# Build context must be the REPO ROOT (it copies shared/ too):
#   build: { context: ., dockerfile: advisor/Dockerfile }
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/opt/hf
WORKDIR /app

# CPU-only torch first (the default wheel pulls ~2 GB of CUDA libs we don't need)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY advisor/requirements.txt .
RUN pip install -r requirements.txt

# bake the embedding model into the image so startup needs no internet
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY advisor/ ./
COPY shared/ ./shared/

RUN useradd -m app && mkdir -p /data/chroma && chown -R app /data /opt/hf
USER app
VOLUME /data/chroma
EXPOSE 8003
HEALTHCHECK --interval=15s --timeout=3s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8003/health').status==200 else 1)"
# ONE worker: the rate limiter keeps its counters in memory
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "1"]
