import mysql.connector

import os
from dotenv import load_dotenv
load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_DATABASE'),
    'port': os.getenv('DB_PORT')
}




def fetch_batch_recordings(batch):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor(dictionary=True)  # use dictionary cursor
        query = "SELECT * FROM whiteboxqa.recording WHERE batchname = %s;"
        cursor.execute(query, (batch,))
        data = cursor.fetchall()
        return data
    finally:
        conn.close()

def fetch_keyword_recordings(keyword):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor(dictionary=True)  # use dictionary cursor
        query = "SELECT * FROM whiteboxqa.recording WHERE description LIKE %s;"
        cursor.execute(query, ('%' + keyword + '%',))
        data = cursor.fetchall()
        return data
    finally:
        conn.close()

        
def fetch_keyword_presentation(keyword):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        type_mapping = {
            "Presentations": "P",
            "Cheatsheets": "C",
            "Diagrams": "D",
            "Installations": "I",
            "Templates": "T",
            "Books": "B",
            "Softwares": "S",
            "Miscellaneous": "M"
        }
        type_code = type_mapping.get(keyword)
        if type_code:
            query = "SELECT * FROM whiteboxqa.course_material WHERE type = %s;"
            cursor.execute(query, (type_code,))
            data = cursor.fetchall()
            return data
        else:
            return "Invalid keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Miscellaneous"
    finally:
        conn.close()