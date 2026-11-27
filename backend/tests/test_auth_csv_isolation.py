from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app, get_db, limiter
from app.database import Base
from app.security import SECRET_KEY

@pytest.fixture
def client():
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    def db():
        with Session() as session:
            yield session
    app.dependency_overrides[get_db] = db
    old = limiter.enabled
    limiter.enabled = False
    try:
        yield TestClient(app)
    finally:
        limiter.enabled = old
        app.dependency_overrides.clear()
        engine.dispose()

def register(c, email):
    r=c.post('/auth/register',json={'email':email,'password':'TestPassword123!'})
    assert r.status_code == 201, r.text
    return r.json()

def headers(t): return {'Authorization':'Bearer '+t['access_token']}

def test_auth_errors_and_refresh(client):
    t=register(client,'a@example.test')
    assert client.post('/auth/login',json={'email':'a@example.test','password':'wrongpass'}).status_code==401
    assert client.post('/auth/refresh',json={'refresh_token':t['refresh_token']}).status_code==200
    expired=jwt.encode({'sub':'1','type':'access','exp':datetime.now(timezone.utc)-timedelta(seconds=1)},SECRET_KEY,algorithm='HS256')
    assert client.get('/transactions',headers={'Authorization':'Bearer '+expired}).status_code==401
    assert client.get('/transactions',headers={'Authorization':'Bearer '+t['refresh_token']}).status_code==401

def test_csv_and_user_isolation(client):
    a=register(client,'a@example.test'); b=register(client,'b@example.test')
    csv='timestamp,amount,merchant,txn_type\n2026-11-01T12:00:00,150,Store,debit\n'
    def upload(body): return client.post('/transactions/upload',headers=headers(a),files={'file':('test.csv',body,'text/csv')})
    assert upload(csv).json()['imported']==1
    assert upload(csv).json()['duplicates']==1
    assert upload(csv.replace('150','-1')).status_code==422
    assert upload('bad,header\n1,2').status_code==422
    rows=client.get('/transactions',headers=headers(a)).json()
    assert len(rows)==1
    assert client.get('/transactions',headers=headers(b)).json()==[]
    assert client.get('/transactions/'+str(rows[0]['id']),headers=headers(b)).status_code==404
    goal=client.post('/goals',headers=headers(a),json={'name':'Demo','target':100,'saved':10}).json()
    assert client.delete('/goals/'+str(goal['id']),headers=headers(b)).status_code==404

def test_csv_fraud_fields_persist(client):
    from app.member_d_models import Transaction

    t = register(client, 'fraud@example.test')
    body = (
        'timestamp,amount,merchant,txn_type,balance,device,location\n'
        '2026-11-01T12:00:00,150,Store,debit,4850,Phone-A,Noida\n'
    )

    response = client.post(
        '/transactions/upload',
        headers=headers(t),
        files={'file': ('test.csv', body, 'text/csv')}
    )
    assert response.status_code == 200
    assert response.json()['imported'] == 1

    dependency = app.dependency_overrides[get_db]
    session = dependency()
    db = next(session)
    try:
        row = db.query(Transaction).one()
        assert float(row.balance) == 4850
        assert row.device == 'Phone-A'
        assert row.location == 'Noida'
    finally:
        session.close()
