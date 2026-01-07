# //wbl-backend\Dockerfile

FROM python:3.11-slim

WORKDIR /app

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