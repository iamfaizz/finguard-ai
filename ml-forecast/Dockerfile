FROM python:3.11-slim
WORKDIR /app
COPY requirements-integration.txt .
RUN pip install --no-cache-dir -r requirements-integration.txt
COPY projecttt.py forecast_service.py ./
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "forecast_service:app", "--host", "0.0.0.0", "--port", "8000"]
