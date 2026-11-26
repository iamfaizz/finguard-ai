import asyncio, csv, hashlib, io, os
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
import httpx, jwt
from fastapi import FastAPI, Depends, HTTPException, UploadFile, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, func, text, or_, and_
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from .database import Base, engine, SessionLocal, get_db
from .member_d_models import User, Transaction, Goal, ChatMessage
from .security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token

class Credentials(BaseModel):
    email: str = Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$', max_length=254)
    password: str = Field(min_length=8,max_length=128)
class Refresh(BaseModel):
    refresh_token: str
class Row(BaseModel):
    timestamp: datetime
    amount: Decimal = Field(gt=0,max_digits=12,decimal_places=2)
    merchant: str = Field(min_length=1,max_length=200)
    txn_type: Literal['credit','debit'] = 'debit'
class GoalInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    target: Decimal = Field(gt=0,max_digits=12,decimal_places=2)
    saved: Decimal = Field(default=0,ge=0,max_digits=12,decimal_places=2)
    target_date: date | None = None
class Feedback(BaseModel):
    status: Literal['confirmed','dismissed']

async def service(url, payload):
    async with httpx.AsyncClient(timeout=2) as client:
        for _ in range(2):
            try:
                r = await client.post(url,json=payload); r.raise_for_status(); return r.json()
            except (httpx.HTTPError, ValueError):
                await asyncio.sleep(.1)
    raise RuntimeError('Service unavailable')

def serialize(t):
    return dict(id=t.id, timestamp=t.timestamp.isoformat(), amount=str(t.amount), merchant=t.merchant, category=t.category, txn_type=t.txn_type, status=t.status, score=str(t.score) if t.score is not None else None, reason=t.reason)

async def retry_pending():
    while True:
        try:
            with SessionLocal() as db:
                rows=db.scalars(select(Transaction).where(Transaction.status=='pending_review').order_by(Transaction.timestamp, Transaction.id).limit(20)).all()
                for t in rows:
                    try:
                        cat=await service(os.getenv('FORECAST_URL','http://ml-forecast:8000')+'/categorize', {'merchant':t.merchant,'narration':t.merchant})
                        t.category=cat['category']
                        from .fraud_adapter import score_payload
                        history = db.scalars(select(Transaction).where(
                            Transaction.user_id == t.user_id,
                            or_(Transaction.timestamp < t.timestamp,
                                and_(Transaction.timestamp == t.timestamp, Transaction.id <= t.id))
                        ).order_by(Transaction.timestamp, Transaction.id)).all()
                        result = await service(os.getenv('FRAUD_URL','http://ml-fraud:8001')+'/score', score_payload(history))
                        probability = float(result['fraud_probability'])
                        risk = result['risk_level']
                        reasons = result['reasons']
                        if not 0 <= probability <= 1 or risk not in ('LOW','MEDIUM','HIGH') or not isinstance(reasons,list) or not all(isinstance(r,str) for r in reasons):
                            raise ValueError('Invalid fraud response')
                        t.score = Decimal(str(probability))
                        t.risk_level = risk
                        t.fraud_reasons = reasons
                        t.reason = '; '.join(reasons)
                        t.model_version = result['model_version']
                        t.status = 'flagged' if risk in ('MEDIUM','HIGH') else 'cleared'
                    except (RuntimeError,KeyError,ValueError,TypeError,ArithmeticError):
                        pass
                    db.commit()
        except Exception:
            import logging
            logging.exception('Pending review worker failed')
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(retry_pending())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError): await task

app=FastAPI(title='FinGuard AI API',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv('FRONTEND_ORIGIN','http://localhost:5173')],allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Authorization','Content-Type'])
limiter=Limiter(key_func=get_remote_address); app.state.limiter=limiter
app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler)
bearer=HTTPBearer(auto_error=False)
def token_user(token,kind,db):
    try:
        p=decode_token(token)
        if p['type']!=kind or 'exp' not in p: raise ValueError()
        user=db.get(User,int(p['sub']))
        if user is None or not user.is_active: raise ValueError()
        return user
    except (jwt.PyJWTError,KeyError,ValueError,TypeError): raise HTTPException(401,'Invalid or expired token')
def current_user(auth: HTTPAuthorizationCredentials=Depends(bearer),db=Depends(get_db)):
    if not auth: raise HTTPException(401,'Login required')
    return token_user(auth.credentials,'access',db)
def tokens(u): return {'access_token':create_access_token(u.id),'refresh_token':create_refresh_token(u.id),'token_type':'bearer'}
@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/auth/register',status_code=201)
@limiter.limit('5/minute')
def register(request:Request, body:Credentials,db=Depends(get_db)):
    u=User(email=body.email.lower(),password=hash_password(body.password)); db.add(u)
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,'Email already registered')
    return tokens(u)
@app.post('/auth/login')
@limiter.limit('10/minute')
def login(request:Request,body:Credentials,db=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==body.email.lower()))
    if not u or not verify_password(body.password,u.password): raise HTTPException(401,'Invalid credentials')
    return tokens(u)
@app.post('/auth/refresh')
@limiter.limit('30/minute')
def refresh(request:Request,body:Refresh,db=Depends(get_db)): return tokens(token_user(body.refresh_token,'refresh',db))
@app.post('/transactions/upload')
async def upload(file:UploadFile,u=Depends(current_user),db=Depends(get_db)):
    raw=await file.read(5*1024*1024+1)
    if len(raw)>5*1024*1024: raise HTTPException(413,'Maximum CSV size is 5 MB')
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if not {'timestamp','amount','merchant'}.issubset(reader.fieldnames or []): raise ValueError('Required columns: timestamp, amount, merchant')
        rows=[]
        for i,r in enumerate(reader,2):
            if len(rows) >= 5000: raise ValueError("Maximum 5000 CSV rows")
            try: rows.append(Row.model_validate(r))
            except ValidationError: raise ValueError(f'Invalid CSV row {i}')
    except (ValueError,csv.Error) as e: raise HTTPException(422,str(e))
    if not rows: raise HTTPException(422,'Empty CSV')
    if db.bind.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        from sqlalchemy.dialects.postgresql import insert
    values=[]
    for r in rows:
        ts=r.timestamp.replace(tzinfo=timezone.utc) if r.timestamp.tzinfo is None else r.timestamp.astimezone(timezone.utc)
        key=hashlib.sha256(f'{u.id}|{ts.isoformat()}|{r.amount:.2f}|{r.merchant.strip().casefold()}'.encode()).hexdigest()
        values.append(dict(user_id=u.id,timestamp=ts,amount=r.amount,merchant=r.merchant,txn_type=r.txn_type,fingerprint=key,status='pending_review',category='Uncategorized'))
    count=0
    for start in range(0,len(values),500):
        result=db.execute(insert(Transaction).values(values[start:start+500]).on_conflict_do_nothing(index_elements=['user_id','fingerprint']).returning(Transaction.id)); count+=len(result.all())
    db.commit(); return {'imported':count,'duplicates':len(rows)-count,'status':'pending_review'}
@app.get('/transactions')
def transactions(q:str='',category:str='',offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),u=Depends(current_user),db=Depends(get_db)):
    stmt=select(Transaction).where(Transaction.user_id==u.id)
    if q: stmt=stmt.where(Transaction.merchant.ilike('%'+q+'%'))
    if category: stmt=stmt.where(Transaction.category==category)
    return [serialize(t) for t in db.scalars(stmt.order_by(Transaction.timestamp.desc()).offset(offset).limit(limit))]
@app.get('/transactions/{id}')
def transaction(id:int,u=Depends(current_user),db=Depends(get_db)):
    t=db.scalar(select(Transaction).where(Transaction.id==id,Transaction.user_id==u.id))
    if not t: raise HTTPException(404,'Transaction not found')
    return serialize(t)
@app.get('/dashboard')
def dashboard(u=Depends(current_user),db=Depends(get_db)):
    base=Transaction.user_id==u.id
    totals=dict(db.execute(select(Transaction.txn_type,func.sum(Transaction.amount)).where(base).group_by(Transaction.txn_type)).all())
    spend=totals.get('debit',Decimal(0)); income=totals.get('credit',Decimal(0))
    cats=db.execute(select(Transaction.category,func.sum(Transaction.amount)).where(base,Transaction.txn_type=='debit').group_by(Transaction.category)).all()
    month=func.strftime('%Y-%m',Transaction.timestamp) if db.bind.dialect.name == 'sqlite' else func.to_char(Transaction.timestamp,'YYYY-MM')
    trend=db.execute(select(month,func.sum(Transaction.amount)).where(base,Transaction.txn_type=='debit').group_by(month).order_by(month)).all()
    alerts=db.scalars(select(Transaction).where(base,Transaction.status=='flagged').order_by(Transaction.timestamp.desc()).limit(10)).all()
    return dict(spend=str(spend),income=str(income),savings_rate=str((income-spend)*100/income if income else 0),alert_count=db.scalar(select(func.count()).select_from(Transaction).where(base,Transaction.status=='flagged')),categories=[dict(name=k,value=str(v)) for k,v in cats],trend=[dict(month=k,value=str(v)) for k,v in trend],alerts=[serialize(t) for t in alerts])
@app.get('/alerts')
def alerts(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),u=Depends(current_user),db=Depends(get_db)):
    return [serialize(t) for t in db.scalars(select(Transaction).where(Transaction.user_id==u.id,Transaction.status=='flagged').order_by(Transaction.timestamp.desc()).offset(offset).limit(limit))]
@app.post('/alerts/{id}/feedback')
def feedback(id:int,body:Feedback,u=Depends(current_user),db=Depends(get_db)):
    t=db.scalar(select(Transaction).where(Transaction.id==id,Transaction.user_id==u.id,Transaction.status=='flagged'))
    if not t: raise HTTPException(404,'Alert not found')
    t.status=body.status; db.commit(); return serialize(t)
def goal_dict(g): return dict(id=g.id,name=g.name,target=str(g.target),saved=str(g.saved),target_date=g.target_date)
@app.get('/goals')
def goals(u=Depends(current_user),db=Depends(get_db)): return [goal_dict(g) for g in db.scalars(select(Goal).where(Goal.user_id==u.id))]
@app.post('/goals',status_code=201)
def create_goal(body:GoalInput,u=Depends(current_user),db=Depends(get_db)):
    g=Goal(user_id=u.id,**body.model_dump()); db.add(g); db.commit(); return goal_dict(g)
def own_goal(id,u,db):
    g=db.scalar(select(Goal).where(Goal.id==id,Goal.user_id==u.id))
    if not g: raise HTTPException(404,'Goal not found')
    return g
@app.put('/goals/{id}')
def update_goal(id:int,body:GoalInput,u=Depends(current_user),db=Depends(get_db)):
    g=own_goal(id,u,db)
    for k,v in body.model_dump(exclude_unset=True).items(): setattr(g,k,v)
    db.commit(); return goal_dict(g)
@app.delete('/goals/{id}')
def delete_goal(id:int,u=Depends(current_user),db=Depends(get_db)):
    db.delete(own_goal(id,u,db)); db.commit(); return {'deleted':True}


@app.get('/forecast')
async def forecast(u=Depends(current_user), db=Depends(get_db)):
    from .ml_adapter import forecast_payload
    rows=db.scalars(select(Transaction).where(Transaction.user_id==u.id).order_by(Transaction.timestamp)).all()
    try:
        return await service(os.getenv('FORECAST_URL','http://ml-forecast:8000')+'/forecast', forecast_payload(rows))
    except RuntimeError:
        raise HTTPException(503,'Forecast service unavailable')

# Register Member B's actual router when present. Do not suppress broken imports.
from importlib.util import find_spec
if find_spec(__package__ + '.routers.advisor_tools') is not None:
    from .routers import advisor_tools
    app.include_router(advisor_tools.router)
