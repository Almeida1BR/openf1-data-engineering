FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY config config
COPY src src
COPY sql sql
CMD ["python", "-m", "src.pipeline", "--skip-ingestion", "--load-database"]
