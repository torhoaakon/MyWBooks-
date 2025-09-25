web: uvicorn mywbooks.api:app --host 0.0.0.0 --port 8000 --reload
worker: dramatiq mywbooks.tasks --processes 1 --threads 4
redis:  redis-server --save "" --appendonly no
