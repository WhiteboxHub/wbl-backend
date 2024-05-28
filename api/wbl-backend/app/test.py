import mysql.connector
from mysql.connector import Error
import os


# Load environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    # Get database connection details from environment variables
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT', '3306')  # Default port is 3306 if DB_PORT is not set
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME')

    print(db_user)

    connection = mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name
    )
    
    if connection.is_connected():
        print("Connected to MySQL server")
except Error as e:
    print(f"Error: {e}")
