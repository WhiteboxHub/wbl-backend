# use the offical python image with python 3.9 as the base image
FROM python:3.9

# set the working directory inside the container to /app
WORKDIR /APP

#copy the requirements.txt.
COPY requirments.txt .

# install the python dependencies specified in requirements.txt
# no-chace-dir: dont cachhe the installed packages to save space
#upgrade: upgrage all specified packages to the newest available version

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirments.txt

# copy the entire app directory (containing main.py and any other files) from the local directory to the /app directory inside the container in the future
COPY . /APP 

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV PYTHONPATH=/APP

#set the command to run the appilication using uvicorn
#"main:app" tells uvicorn to look for an object called app in a module named main (main.py)
# Run the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
