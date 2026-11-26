FROM python:3.11-slim

WORKDIR /app

COPY requirements-docker.txt .

RUN pip install --no-cache-dir -r requirements-docker.txt

COPY artifacts/ ./artifacts/
COPY src/ ./src/

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8001"]
