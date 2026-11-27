FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY ml-fraud/src/features.py ./fraud_features.py
COPY shared/ ./shared/
COPY backend/tests/ ./tests/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini .

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
