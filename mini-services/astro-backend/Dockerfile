# AstroTrader FastAPI backend
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 ASTRO_CACHE_DIR=/data
COPY requirements.txt requirements-ml.txt ./
ARG WITH_ML=1
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$WITH_ML" = "1" ]; then pip install --no-cache-dir -r requirements-ml.txt || true; fi
COPY app ./app
VOLUME /data
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
