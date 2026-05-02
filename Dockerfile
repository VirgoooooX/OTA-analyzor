FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATA_DIR=/app/data
ENV UPLOAD_DIR=/app/uploads
ENV TAGS_FILE=/app/config/tags.json
ENV DB_PATH=/app/config/ota.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fontconfig libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analysis.py main.py ./
COPY app/ ./app/
COPY static ./static

RUN mkdir -p /app/data /app/uploads /app/config \
    && echo '{}' > /app/config/tags.json

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host ${HOST} --port ${PORT}"]
