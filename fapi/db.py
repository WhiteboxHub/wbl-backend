from fapi.utils import md5_hash,verify_md5_hash,hash_password
import mysql.connector
from fastapi import HTTPException, status
from mysql.connector import Error
import os
from typing import Optional,Dict
import asyncio
from dotenv import load_dotenv


load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'port': os.getenv('DB_PORT')
}

# Async function to insert a user into the database
async def insert_user(uname: str, passwd: str, dailypwd: Optional[str] = None, team: str = None, level: str = None, 
                      instructor: str = None, override: str = None, status: str = None, lastlogin: str = None, 
                      logincount: str = None, fullname: str = None, phone: str = None, address: str = None, 
                      city: str = None, Zip: str = None, country: str = None, message: str = None, 
                      registereddate: str = None, level3date: str = None, candidate_info: Dict[str, Optional[str]] = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        
        # Insert into authuser table
        query1 = """
            INSERT INTO whiteboxqa.authuser (
                uname, passwd, dailypwd, team, level, instructor, override, status, 
                lastlogin, logincount, fullname, phone, address, city, Zip, country, 
                message, registereddate, level3date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        values1 = (
            uname, passwd, dailypwd, team, level, instructor, override, status, 
            lastlogin, logincount, fullname, phone, address, city, Zip, country, 
            message, registereddate, level3date
        )
        await loop.run_in_executor(None, cursor.execute, query1, values1)
        
        # Insert into candidate table
        query2 = """
            INSERT INTO whiteboxqa.candidate (
                name, enrolleddate, email, course, phone, status, address, city, country, zip
            ) VALUES (%s, %s, %s, 'QA', %s,'active', %s, %s, %s, %s);
        """
        values2 = (
            candidate_info['name'], candidate_info['enrolleddate'], candidate_info['email'],
            candidate_info['phone'], candidate_info['address'], 
            candidate_info['city'], candidate_info['country'], candidate_info['zip']
        )
        await loop.run_in_executor(None, cursor.execute, query2, values2)

        #get the last inserted ID to for candidate_ID
        candidate_id = cursor.lastrowid

         ## Insert the candidate_id into the candidate_resume table
        query3 = """
            INSERT INTO whiteboxqa.candidate_resume (
                candidate_id
            ) VALUES (%s);
        """
        values3 = (candidate_id,)
        await loop.run_in_executor(None, cursor.execute, query3, values3)

        conn.commit()
    except Error as e:
        # print(f"Error inserting user: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error inserting user")
    finally:
        cursor.close()
        conn.close()

async def update_login_info(user_id: int):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = """
            UPDATE whiteboxqa.authuser 
            SET lastlogin = NOW(), logincount = logincount + 1 
            WHERE id = %s;
        """
        await loop.run_in_executor(None, cursor.execute, query, (user_id,))
        conn.commit()
    except Error as e:
        # print(f"Error updating login info: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error updating login info")
    finally:
        cursor.close()
        conn.close()

async def insert_login_history(user_id: int, ipaddress: str, useragent: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO whiteboxqa.loginhistory (loginid, logindatetime, ipaddress, useragent) 
            VALUES (%s, NOW(), %s, %s);
        """
        await loop.run_in_executor(None, cursor.execute, query, (user_id, ipaddress, useragent))
        conn.commit()
    except Error as e:
        # print(f"Error inserting login history: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error inserting login history")
    finally:
        cursor.close()
        conn.close()
    

#fucntion to merge batchs
def merge_batches(q1_response,q2_response):
    # Combine the two lists
    all_batches = q1_response + q2_response    
    seen_batches = set()
    unique_batches = []


    for batch in all_batches:
        # print(batch['batchname'])
        if batch['batchname'] not in seen_batches:
            seen_batches.add(batch['batchname'])
            unique_batches.append(batch)
    # Sort unique_batches by batchname in descending order (latest to oldest)
    unique_batches.sort(key=lambda x: x['batchname'], reverse=True)
    return unique_batches

#function to fetch batch names based on courses
async def fetch_course_batches(subject:str=None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        batchquery = f"""
                SELECT batchname,batchid 
                FROM whiteboxqa.new_batch
                WHERE subject = '{subject}'
                GROUP BY batchname
                ORDER BY batchname DESC;
                """
        await loop.run_in_executor(None, cursor.execute, batchquery)
        r1 = cursor.fetchall()
        return r1
    except Error as e:
        # print(f"Error: {e}")
        return []
    finally:
        conn.close()


async def fetch_subject_batch_recording(subject: str = None, batchid: int = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = f"""
                SELECT DISTINCT nr.id, nr.batchname, nr.description, nr.type, nr.classdate, nr.link, nr.videoid, nr.subject, nr.filename, nr.lastmoddatetime, nr.new_subject_id
                FROM new_recording nr
                JOIN new_recording_batch rb ON nr.id = rb.recording_id
                JOIN new_batch b ON rb.batch_id = b.batchid
                JOIN new_course_subject ncs ON b.courseid = ncs.course_id
                JOIN new_course nc ON ncs.course_id = nc.id
                WHERE nc.alias = '{subject}'
                AND b.batchid = {batchid}
                AND nr.new_subject_id IN (
                SELECT subject_id
                FROM new_course_subject
                WHERE course_id = (
                SELECT id
                FROM new_course
                WHERE alias = '{subject}'
                )
                );
                """
        await loop.run_in_executor(None, cursor.execute, query)
        recordings = cursor.fetchall()
        return recordings
    finally:
        conn.close()


async def fetch_keyword_recordings(subject: str, keyword: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
                SELECT DISTINCT nr.id, nr.batchname, nr.description, nr.type, nr.classdate, nr.link, nr.videoid, nr.subject, nr.filename, nr.lastmoddatetime, nr.new_subject_id
                FROM new_recording nr
                JOIN new_recording_batch rb ON nr.id = rb.recording_id
                JOIN new_batch b ON rb.batch_id = b.batchid
                JOIN new_course_subject ncs ON b.courseid = ncs.course_id
                JOIN new_course nc ON ncs.course_id = nc.id
                WHERE nc.alias = %s
                  AND nr.description LIKE %s
                ORDER BY nr.classdate DESC;
                """
        await loop.run_in_executor(None, cursor.execute, query, (subject, '%' + keyword + '%'))
        recordings = cursor.fetchall()
        return recordings
    finally:
        conn.close()

            
async def fetch_keyword_presentation(search, course):
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
        type_code = type_mapping.get(search)
        if type_code:
            query = """
            SELECT * FROM whiteboxqa.course_material 
            WHERE type = %s AND (courseid = 0 OR courseid = %s) ORDER BY name ASC;
            """
            courseid_mapping = {
                "QA": 1,
                "UI": 2,
                "ML": 4
            }
            selected_courseid = courseid_mapping.get(course.upper())

            await loop.run_in_executor(None, cursor.execute, query, (type_code, selected_courseid))
            data = cursor.fetchall()
            return data
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid search keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Miscellaneous"
            )
    except mysql.connector.Error as err:
        # print(f"Error: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    finally:
        cursor.close()
        conn.close()


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


async def fetch_candidate_id_by_email(email: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT candidateid FROM candidate WHERE email = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (email,))
        result = cursor.fetchone()
        return result
    finally:
        conn.close()


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
            query = "SELECT *  FROM whiteboxqa.session ORDER BY type ASC;"
            await loop.run_in_executor(None, cursor.execute, query)
        sessions = cursor.fetchall()
        return sessions
    finally:
        conn.close()
        

async def user_contact(name: str, email: str = None, phone: str = None,  message: str = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO whiteboxqa.leads (
                name,email, phone,notes) VALUES (%s, %s, %s, %s);
        """
        values = (
            name, email, phone,message)
        await loop.run_in_executor(None, cursor.execute, query, values)
        conn.commit()
    except Error as e:
        # print(f"Error inserting user: {e}")
        raise HTTPException(status_code=409, detail="Response already sent!")
    finally:
        cursor.close()
        conn.close()

def course_content():
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor(dictionary=True)  # Use dictionary=True to get rows as dictionaries
        cursor.execute("SELECT * FROM whiteboxqa.new_course_content")
        data = cursor.fetchall()
        return data 
    finally:
        conn.close()


def unsubscribe_user(email: str) -> (bool, str): # type: ignore
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT remove FROM massemail WHERE email = %s", (email,))
        result = cursor.fetchone()

        if result is None:
            return False, "User not found"

        if result[0] == 'Y':
            return True, "Already unsubscribed"

        cursor.execute("UPDATE massemail SET remove = 'Y' WHERE email = %s", (email,))
        conn.commit()

        return True, "Successfully unsubscribed"
    except Error as e:
        # print(f"Error: {e}")
        return False, "An error occurred"
    finally:
        cursor.close()
        conn.close()
        
        
        
async def update_user_password(uname: str, new_password: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        
        # Hash the new password
        hashed_password = md5_hash(new_password)
        
        # Update the user's password
        query = "UPDATE whiteboxqa.authuser SET passwd = %s WHERE uname = %s;"
        values = (hashed_password, uname)
        
        await loop.run_in_executor(None, cursor.execute, query, values)
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    except Error as e:
        # print(f"Error updating password: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail="Error updating password")
    finally:
        cursor.close()
        conn.close()      
        
async def get_user_by_email(email: str):
    try:
        # Establish connection
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            cursor = conn.cursor(dictionary=True)  # Use dictionary=True to get results as dictionaries
            query = "SELECT * FROM authuser WHERE uname = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            return result
    except Error as e:
        # print(f"Error: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()        

async def update_user_password(email: str, new_password: str):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        hashed_password = hash_password(new_password)
        cursor.execute("UPDATE authuser SET passwd = %s WHERE uname = %s", (hashed_password, email))
        conn.commit()
    finally:
        cursor.close()
        conn.close()