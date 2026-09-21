# //wbl-backend\Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg for audio-to-video container rendering)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Cloud Run expects the container to listen on $PORT
ENV PORT=8080
EXPOSE 8080

# Run FastAPI
CMD uvicorn fapi.main:app --host 0.0.0.0 --port $PORT