# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Install python-dotenv if you need it for local development
RUN pip install python-dotenv

# Make port 8000 available to the world outside this container
EXPOSE 8000

# # Copy the .env file to the working directory
COPY .env .env

# Run the FastAPI server with reload option
CMD ["uvicorn", "fapi.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

