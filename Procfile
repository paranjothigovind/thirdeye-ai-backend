web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.ingestion.workers worker --loglevel=INFO