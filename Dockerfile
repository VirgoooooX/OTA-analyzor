FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATA_DIR=/app/data
ENV UPLOAD_DIR=/app/uploads
ENV TAGS_FILE=/app/tags.json

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fontconfig libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY analysis.py main.py ./
COPY static ./static

# Create default empty tags.json if not provided via build context
RUN echo '{}' > /app/tags.json

RUN mkdir -p /app/data /app/uploads

EXPOSE 8000

CMD ["sh", "-c", "if [ -d /app/tags.json ]; then rm -rf /app/tags.json && echo '{}' > /app/tags.json; fi && uvicorn main:app --host ${HOST} --port ${PORT}"]

