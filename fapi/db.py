# import mysql.connector
# from fastapi import HTTPException, status  
# from mysql.connector import Error
# import os
# from typing import Optional
# from dotenv import load_dotenv
# from auth import md5_hash, verify_md5_hash
# from passlib.context import CryptContext
# import asyncio

# load_dotenv()

# db_config = {
#     'host': os.getenv('DB_HOST'),
#     'user': os.getenv('DB_USER'),
#     'password': os.getenv('DB_PASSWORD'),
#     'database': os.getenv('DB_DATABASE'),
#     'port': os.getenv('DB_PORT')
# }

# # pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# # def insert_user(uname: str, passwd: str, dailypwd: Optional[str] = None, team: str = None, level: str = None, 
# #                 instructor: str = None, override: str = None, status: str = None, lastlogin: str = None, 
# #                 logincount: str = None, fullname: str = None, phone: str = None, address: str = None, 
# #                 city: str = None, Zip: str = None, country: str = None, message: str = None, 
# #                 registereddate: str = None, level3date: str = None):
    
# #     conn = mysql.connector.connect(**db_config)
# #     try:
# #         cursor = conn.cursor()
# #         hashed_password = md5_hash(passwd)  # Hash the password
# #         cursor.execute("""
# #             INSERT INTO whiteboxqa.authuser (
# #                 uname, passwd, dailypwd, team, level, instructor, override, status, 
# #                 lastlogin, logincount, fullname, phone, address, city, Zip, country, 
# #                 message, registereddate, level3date
# #             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
# #         """, (
# #             uname, hashed_password, dailypwd, team, level, instructor, override, status, 
# #             lastlogin, logincount, fullname, phone, address, city, Zip, country, 
# #             message, registereddate, level3date
# #         ))
# #         conn.commit()
# #     except Error as e:
# #         print(f"Error inserting user: {e}")
# #         raise HTTPException(status_code=500, detail="Error inserting user")
# #     finally:
# #         cursor.close()
# #         conn.close()
# async def insert_user(uname: str, passwd: str, dailypwd: Optional[str] = None, team: str = None, level: str = None, 
#                 instructor: str = None, override: str = None, status: str = None, lastlogin: str = None, 
#                 logincount: str = None, fullname: str = None, phone: str = None, address: str = None, 
#                 city: str = None, Zip: str = None, country: str = None, message: str = None, 
#                 registereddate: str = None, level3date: str = None):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
#         query = """
#             INSERT INTO whiteboxqa.authuser (
#                 uname, passwd, dailypwd, team, level, instructor, override, status, 
#                 lastlogin, logincount, fullname, phone, address, city, Zip, country, 
#                 message, registereddate, level3date
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
#         """
#         values = (
#             uname, passwd, dailypwd, team, level, instructor, override, status, 
#             lastlogin, logincount, fullname, phone, address, city, Zip, country, 
#             message, registereddate, level3date
#         )
#         await loop.run_in_executor(None, cursor.execute, query, values)
#         conn.commit()
#     except Error as e:
#         print(f"Error inserting user: {e}")
#         raise HTTPException(status_code=500, detail="Error inserting user")
#     finally:
#         cursor.close()  
#         conn.close()
        
                
# # def fetch_batches():
# #     conn = mysql.connector.connect(**db_config)
# #     try:
# #         cursor = conn.cursor(dictionary=True)
# #         query = """
# #             SELECT batchname
# #             FROM whiteboxqa.recording
# #             GROUP BY batchname
# #             ORDER BY batchname DESC;
# #         """
# #         cursor.execute(query)
# #         batches = cursor.fetchall()
# #         return batches
# #     finally:
# #         conn.close()
# async def fetch_batches():
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = """
#             SELECT batchname
#             FROM whiteboxqa.recording
#             GROUP BY batchname
#             ORDER BY batchname DESC;
#         """
#         await loop.run_in_executor(None, cursor.execute, query)
#         batches = cursor.fetchall()
#         return batches
#     finally:
#         conn.close()


# # def fetch_batch_recordings(batch):
# #     conn = mysql.connector.connect(**db_config)
# #     try:
# #         cursor = conn.cursor(dictionary=True)  # use dictionary cursor
# #         query = "SELECT * FROM whiteboxqa.recording WHERE batchname = %s;"
# #         cursor.execute(query, (batch,))
# #         data = cursor.fetchall()
# #         return data
# #     finally:
# #         conn.close()
# async def fetch_batch_recordings(batch):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT * FROM whiteboxqa.recording WHERE batchname = %s;"
#         await loop.run_in_executor(None, cursor.execute, query, (batch,))
#         data = cursor.fetchall()
#         return data
#     finally: 
#         conn.close()

# # def fetch_keyword_recordings(keyword):
# #     conn = mysql.connector.connect(**db_config)
# #     try:
# #         cursor = conn.cursor(dictionary=True)  # use dictionary cursor
# #         query = "SELECT * FROM whiteboxqa.recording WHERE description LIKE %s ORDER BY classdate DESC;"
# #         cursor.execute(query, ('%' + keyword + '%',))
# #         data = cursor.fetchall()
# #         return data
# #     finally:
# #         conn.close()
# async def fetch_keyword_recordings(keyword):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)  # use dictionary cursor
#         query = "SELECT * FROM whiteboxqa.recording WHERE description LIKE %s ORDER BY classdate DESC;"
#         await loop.run_in_executor(None, cursor.execute, query, ('%' + keyword + '%',))
#         data = cursor.fetchall()
#         return data
#     finally:
#         conn.close()
        
        
# # def fetch_keyword_presentation(keyword):
# #     conn = mysql.connector.connect(**db_config)
# #     try:
# #         cursor = conn.cursor(dictionary=True)  # use dictionary cursor
# #         type_mapping = {
# #             "Presentations": "P",
# #             "Cheatsheets": "C",
# #             "Diagrams": "D",
# #             "Installations": "I",
# #             "Templates": "T",
# #             "Books": "B",
# #             "Softwares": "S",
# #             "Miscellaneous": "M"
# #         }
# #         type_code = type_mapping.get(keyword)
# #         if type_code:
# #             query = "SELECT * FROM whiteboxqa.course_material WHERE type = %s ORDER BY name ASC;;"
# #             cursor.execute(query, (type_code,))
# #             data = cursor.fetchall()
# #             return data
# #         else:
# #             raise HTTPException(
# #                 status_code=status.HTTP_400_BAD_REQUEST,
# #                 detail="Invalid keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Miscellaneous"
# #             )
# #     except mysql.connector.Error as err:
# #         print(f"Error: {err}")
# #         raise HTTPException(
# #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# #             detail="Database error occurred"
# #         )
# #     finally:
# #         cursor.close()
# #         conn.close()
# async def fetch_keyword_presentation(keyword):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)  # use dictionary cursor
#         type_mapping = {
#             "Presentations": "P",
#             "Cheatsheets": "C",
#             "Diagrams": "D",
#             "Installations": "I",
#             "Templates": "T",
#             "Books": "B",
#             "Softwares": "S",
#             "Miscellaneous": "M"
#         }
#         type_code = type_mapping.get(keyword)
#         if type_code:
#             query = "SELECT * FROM whiteboxqa.course_material WHERE type = %s;"
#             await loop.run_in_executor(None, cursor.execute, query, (type_code,))
#             data = cursor.fetchall()
#             return data
#         else:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Invalid keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Miscellaneous"
#             )
#     except mysql.connector.Error as err:
#         print(f"Error: {err}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Database error occurred"
#         )
#     finally:
#         cursor.close()
#         conn.close()


# # def get_user_by_username(uname: str):
# #     conn = mysql.connector.connect(**db_config)
# #     try:
# #         cursor = conn.cursor(dictionary=True)  # use dictionary cursor
# #         # cursor.execute("SELECT id, uname, passwd FROM whiteboxqa.authuser WHERE uname = %s;", (uname,))
# #         cursor.execute("SELECT * FROM whiteboxqa.authuser WHERE uname = %s;", (uname,))
# #         result = cursor.fetchone()
# #         return result
# #     finally:
# #         conn.close()
# async def get_user_by_username(uname: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)  # use dictionary cursor
#         query = ("SELECT * FROM whiteboxqa.authuser WHERE uname = %s;", (uname))
#         await loop.run_in_executor(None, cursor.execute, query, (uname,))
#         result = cursor.fetchone()
#         return result
#     finally:
#         conn.close()
        

# async def fetch_sessions_by_type(category: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT * FROM whiteboxqa.session WHERE type = %s;"
#         await loop.run_in_executor(None, cursor.execute, query, (category,))
#         sessions = cursor.fetchall()
#         return sessions
#     finally:
#         conn.close()
        

# # def verify_password(plain_password, hashed_password):
# #        return pwd_context.verify(plain_password, hashed_password)


# def verify_password(plain_password, hashed_password):
#     return pwd_context.verify(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))




import mysql.connector
from fastapi import HTTPException, status
from mysql.connector import Error
import os
from typing import Optional
from dotenv import load_dotenv
from auth import md5_hash, verify_md5_hash
from passlib.context import CryptContext
import asyncio

load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_DATABASE'),
    'port': os.getenv('DB_PORT')
}

# Async function to insert a user into the database
async def insert_user(uname: str, passwd: str, dailypwd: Optional[str] = None, team: str = None, level: str = None, 
                      instructor: str = None, override: str = None, status: str = None, lastlogin: str = None, 
                      logincount: str = None, fullname: str = None, phone: str = None, address: str = None, 
                      city: str = None, Zip: str = None, country: str = None, message: str = None, 
                      registereddate: str = None, level3date: str = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO whiteboxqa.authuser (
                uname, passwd, dailypwd, team, level, instructor, override, status, 
                lastlogin, logincount, fullname, phone, address, city, Zip, country, 
                message, registereddate, level3date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        values = (
            uname, passwd, dailypwd, team, level, instructor, override, status, 
            lastlogin, logincount, fullname, phone, address, city, Zip, country, 
            message, registereddate, level3date
        )
        await loop.run_in_executor(None, cursor.execute, query, values)
        conn.commit()
    except Error as e:
        print(f"Error inserting user: {e}")
        raise HTTPException(status_code=500, detail="Error inserting user")
    finally:
        cursor.close()
        conn.close()

# Async function to fetch batch names from the database
async def fetch_batches():
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT batchname
            FROM whiteboxqa.recording
            GROUP BY batchname
            ORDER BY batchname DESC;
        """
        await loop.run_in_executor(None, cursor.execute, query)
        batches = cursor.fetchall()
        return batches
    finally:
        conn.close()

# Async function to fetch recordings for a specific batch
async def fetch_batch_recordings(batch):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM whiteboxqa.recording WHERE batchname = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (batch,))
        data = cursor.fetchall()
        return data
    finally:
        conn.close()

# Async function to fetch recordings based on a keyword
async def fetch_keyword_recordings(keyword):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM whiteboxqa.recording WHERE description LIKE %s ORDER BY classdate DESC;"
        await loop.run_in_executor(None, cursor.execute, query, ('%' + keyword + '%',))
        data = cursor.fetchall()
        return data
    finally:
        conn.close()

# Async function to fetch presentations based on a keyword
async def fetch_keyword_presentation(keyword):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
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
            query = "SELECT * FROM whiteboxqa.course_material WHERE type = %s ORDER BY name ASC;"
            await loop.run_in_executor(None, cursor.execute, query, (type_code,))
            data = cursor.fetchall()
            return data
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Miscellaneous"
            )
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    finally:
        cursor.close()
        conn.close()

# Async function to fetch a user by username
async def get_user_by_username(uname: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM whiteboxqa.authuser WHERE uname = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (uname,))
        result = cursor.fetchone()
        return result
    finally:
        conn.close()

# Async function to fetch sessions by category
# async def fetch_sessions_by_type(category: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT * FROM whiteboxqa.session WHERE type = %s;"
#         await loop.run_in_executor(None, cursor.execute, query, (category,))
#         sessions = cursor.fetchall()
#         return sessions
#     finally:
#         conn.close()


# Async function to fetch sessions by category
async def fetch_sessions_by_type(category: str = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        if category:
            query = "SELECT  * FROM whiteboxqa.session WHERE type = %s ORDER BY sessiondate DESC;"
            await loop.run_in_executor(None, cursor.execute, query, (category,))
        else:
            query = "SELECT DISTINCT type FROM whiteboxqa.session ORDER BY type ASC;"
            await loop.run_in_executor(None, cursor.execute, query)
        sessions = cursor.fetchall()
        return sessions
    finally:
        conn.close()

# async def fetch_sessions_by_type(category: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT * FROM whiteboxqa.session WHERE type = %s;"
#         await loop.run_in_executor(None, cursor.execute, query, (category,))
#         sessions = cursor.fetchall()
#         return sessions
#     finally:
#         conn.close()
