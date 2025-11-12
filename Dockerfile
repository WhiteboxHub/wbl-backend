# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install python-dotenv if needed for local development
RUN pip install --no-cache-dir python-dotenv

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Environment variable for Ollama (set dynamically in Kubernetes)
# ENV OLLAMA_HOST=http://ollama-service:11434

# Run the FastAPI server (production mode)
CMD ["uvicorn", "fapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
