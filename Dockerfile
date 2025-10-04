FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy .git to extract commit hash, then remove it
COPY .git/ ./.git/
RUN git rev-parse --short HEAD > /app/GIT_COMMIT && rm -rf .git

COPY app/ ./app/
COPY config/ ./config/
COPY README.md ./

RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["python", "-m", "app.main"]