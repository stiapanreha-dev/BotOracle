FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set git commit hash (Railway doesn't include .git)
ARG RAILWAY_GIT_COMMIT_SHA
RUN echo "${RAILWAY_GIT_COMMIT_SHA:-unknown}" > /app/GIT_COMMIT

COPY app/ ./app/
COPY config/ ./config/
COPY migrations/ ./migrations/
COPY README.md ./

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "-m", "app.main"]