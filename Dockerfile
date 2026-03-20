FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY app/ app/
COPY policies/ policies/
COPY cases/ cases/

RUN pip install --no-cache-dir ".[ref]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
