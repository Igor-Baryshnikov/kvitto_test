FROM python:3.11-slim
WORKDIR /app
ENV POETRY_VIRTUALENVS_CREATE=false
RUN pip install --no-cache-dir poetry==2.3.2
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main
COPY billing_service ./billing_service
WORKDIR /data
CMD ["sh", "-c", "python -m alembic -c /app/billing_service/alembic.ini upgrade head && exec python -m uvicorn app.main:app --app-dir /app/billing_service --host 0.0.0.0 --port 8000"]
