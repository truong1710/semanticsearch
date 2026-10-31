FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY config.py ./
COPY app ./app
COPY common ./common
COPY core ./core
COPY crawldata ./crawldata
COPY database ./database
COPY embedding ./embedding
COPY indexing ./indexing
COPY retrieval ./retrieval

RUN pip install .

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
