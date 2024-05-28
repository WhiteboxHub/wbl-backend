
from passlib.context import CryptContext
import mysql.connector
from mysql.connector import Error

import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_DATABASE'),
    'port' : os.getenv('DB_PORT')
}



pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def fetch_resources():
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM whiteboxqa.recording;")
        data = cursor.fetchall()
        return data 
    finally:
        conn.close()

def fetch_batch_recordings(batch):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM whiteboxqa.recording WHERE batchname = %s;"
        cursor.execute(query, (batch,))
        data = cursor.fetchall()
        return data 
    
    finally:
        conn.close()


def fetch_keyword_recordings(keyword):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM whiteboxqa.recording WHERE description LIKE %s;"
        cursor.execute(query, ('%' + keyword + '%',))
        data = cursor.fetchall()
        return data 
    
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password FROM signup_db.users WHERE username = %s;", (username,))
        result = cursor.fetchone()
        return result
    finally:
        conn.close()

def insert_user(username: str, password: str, email: str, phone: int, Zip: int, address: str):
    hashed_password = pwd_context.hash(password)
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO signup_db.users (username, password, email, phone, Zip, address) VALUES (%s, %s, %s, %s, %s, %s);", (username, hashed_password, email, phone, Zip, address))
        conn.commit()
        return {"message": "Registration successfully"}
    except Error as e:
        return {"error": f"Error Registering User: {e}"}
    finally:
        conn.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)
