# wbl-backend/fapi/db.py
from fapi.utils.auth_utils import md5_hash,verify_md5_hash,hash_password,verify_reset_token
import mysql.connector
from fastapi import HTTPException, status
from mysql.connector import Error
import os
from typing import Optional,Dict,List
import asyncio
from dotenv import load_dotenv
from datetime import date,datetime,time, timedelta  
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from urllib.parse import quote
load_dotenv()
raw_password = os.getenv('DB_PASSWORD')
encoded_password = quote(raw_password)
db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': raw_password,
    'database': os.getenv('DB_NAME'),
    'port': int(os.getenv('DB_PORT')),
}

DATABASE_URL = (
    f"mysql+pymysql://{db_config['user']}:{encoded_password}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


async def insert_user(
    uname: str,
    passwd: str,
    dailypwd: Optional[str] = None,
    team: str = None,
    level: str = None,
    instructor: str = None,
    override: str = None,
    lastlogin: str = None,
    logincount: str = None,
    fullname: str = None,
    phone: str = None,
    address: str = None,
    city: str = None,
    Zip: str = None,
    country: str = None,
    message: str = None,
    visa_status: Optional[str] = None,
    registereddate: str = None,
    level3date: str = None,
    experience: Optional[str] = None,
    education: Optional[str] = None,
    specialization: Optional[str] = None,
    referby: Optional[str] = None,
    candidate_info: Dict[str, Optional[str]] = None
):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query1 = """
            INSERT INTO whitebox_learning.authuser (


                uname, passwd, dailypwd, team, level, instructor, override, status, 
                lastlogin, logincount, fullname, phone, address, city, Zip, country,

                visa_status,experience, education, specialization, referby,

                `message`, registereddate, level3date
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, 'inactive',
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            );
        """

        values1 = (
            uname, passwd, dailypwd, team, level, instructor, override, 
            lastlogin, logincount, fullname, phone, address, city, Zip.lower() if Zip else None, country,

            visa_status, experience, education, specialization, referby,

            message, registereddate, level3date
        )
        # print(" Values being inserted into DB:", values1)

        await loop.run_in_executor(None, cursor.execute, query1, values1)
        conn.commit()

    except Error as e:
        conn.rollback()
        print("Database Error:", e) 
        raise HTTPException(status_code=500, detail="Error inserting user")

    finally:
        cursor.close()
        conn.close()

# ---------------hkd-----------------------------------

async def insert_lead_new(
    full_name: str,
    phone: Optional[str],
    email: str,
    address: Optional[str],
    workstatus: Optional[str],
    status: Optional[str] = "Open",
    secondary_email: Optional[str] = None,
    secondary_phone: Optional[str] = None,
    closed_date: Optional[date] = None,
    notes: Optional[str] = None
):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))

    try:
        cursor = conn.cursor()

        query = """
            INSERT INTO `lead` (
                full_name, phone, email, address, workstatus,
                status, secondary_email, secondary_phone,
                closed_date, notes
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            );
        """

        values = (
            full_name, phone, email, address, workstatus,
            status, secondary_email, secondary_phone,
            closed_date, notes
        )

        await loop.run_in_executor(None, cursor.execute, query, values)
        conn.commit()

    except Error as e:
        conn.rollback()
        print("Lead Insert Error (lead):", e)
        raise HTTPException(status_code=500, detail="Error inserting into new leads table")

    finally:
        cursor.close()
        conn.close()


# ---------------hkd-----------------------------------

async def get_user_by_username(uname: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM whitebox_learning.authuser WHERE uname = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (uname,))
        result = cursor.fetchone()
        return result
    finally:
        conn.close()   


async def update_login_info(user_id: int):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = """
            UPDATE whitebox_learning.authuser 
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
            INSERT INTO whitebox_learning.loginhistory (loginid, logindatetime, ipaddress, useragent) 
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
                FROM whitebox_learning.batch
                WHERE subject = '{subject}'
                GROUP BY batchname,batchid
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
                FROM recording nr
                JOIN recording_batch rb ON nr.id = rb.recording_id
                JOIN batch b ON rb.batch_id = b.batchid
                JOIN course_subject ncs ON b.courseid = ncs.course_id
                JOIN course nc ON ncs.course_id = nc.id
                WHERE nc.alias = '{subject}'
                AND b.batchid = '{batchid}'
                AND nr.new_subject_id IN (
                SELECT subject_id
                FROM course_subject
                WHERE course_id = (
                SELECT id
                FROM course
                WHERE alias = '{subject}'
                )               
                )
                ORDER BY nr.classdate Desc;
                """
        await loop.run_in_executor(None, cursor.execute, query)
        recordings = cursor.fetchall()
        return recordings
    finally:
        conn.close()


async def fetch_keyword_recordings(subject: str = "", keyword: str = ""):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)

        # Base query with placeholders
        query = """
            SELECT nr.id, nr.batchname, nr.description, nr.type, nr.classdate, nr.link, nr.videoid, nr.subject,
                   nr.filename, nr.lastmoddatetime, nr.new_subject_id,
                   'recording' AS source
            FROM recording nr
            JOIN subject ns ON nr.new_subject_id = ns.id
            JOIN course_subject ncs ON ns.id = ncs.subject_id
            JOIN course nc ON ncs.course_id = nc.id
            WHERE (%s = '' OR nc.alias = %s)
              AND (%s = '' OR nr.description LIKE %s)

            UNION

            SELECT ns.sessionid AS id, ns.title AS batchname, ns.title AS description, ns.type, ns.sessiondate AS classdate, ns.link, ns.videoid, ns.subject,
                   NULL AS filename, ns.lastmoddatetime, ns.subject_id AS new_subject_id,
                   'session' AS source
            FROM session ns
            JOIN course_subject ncs ON ns.subject_id = ncs.subject_id
            JOIN course nc ON ncs.course_id = nc.id
            WHERE (%s = '' OR nc.alias = %s)
              AND (%s = '' OR ns.title LIKE %s)
            ORDER BY classdate DESC;
        """

        # Dynamically adjust parameters for query
        keyword_search = f"%{keyword}%" if keyword else ""
        params = (subject, subject, keyword, keyword_search, subject, subject, keyword, keyword_search)

        # Execute query
        await loop.run_in_executor(None, cursor.execute, query, params)

        # Fetch results
        recordings = cursor.fetchall()
        return recordings
    finally:
        conn.close()


async def insert_vendor(data: Dict):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        sql = """
            INSERT INTO vendor (
                full_name, phone_number, email, city, postal_code, address, country, type, note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            data["full_name"],
            data["phone_number"],
            data.get("email"),
            data.get("city"),
            data.get("postal_code"),
            data.get("address"),
            data.get("country"),
            data["type"],
            data.get("note")
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Internal error:", e)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
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
            "Newsletters": "N"
        }
        type_code = type_mapping.get(search)
        if type_code:
            query = """
            SELECT * FROM whitebox_learning.course_material 
            WHERE type = %s 
            AND (courseid = 0 OR courseid = %s)
            ORDER BY CASE
            WHEN name = 'Software Architecture' THEN 1
            WHEN name = 'SDLC' THEN 2
            WHEN name = 'JIRA Agile' THEN 3
            WHEN name = 'HTTP' THEN 4
            WHEN name = 'Web Services' THEN 5
            WHEN name = 'UNIX - Shell Scripting' THEN 6
            WHEN name = 'MY SQL' THEN 7
            WHEN name = 'Git' THEN 8
            WHEN name = 'json' THEN 9
            ELSE 10 -- Topics not explicitly listed will appear after the specified ones
            END;
            """
            courseid_mapping = {
                "QA": 1,
                "UI": 2,
                "ML": 3
            }
            selected_courseid = courseid_mapping.get(course.upper())

            await loop.run_in_executor(None, cursor.execute, query, (type_code, selected_courseid))
            data = cursor.fetchall()
            return data
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid search keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Newsletters"
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


async def get_user_from_token(token: str):
    # Verify the JWT token and extract the email
    payload = verify_token(token)
    if isinstance(payload, JSONResponse):  # Check if an error response was returned
        raise ValueError("Invalid or expired token")
    
    email = payload.get('sub')  # Assuming 'sub' contains the email or user identifier

    # Query the database to find the user by email
    team = await fetch_user_team(email)
    return team


async def fetch_user_team(email: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Query to check the team column for the user
        query = "SELECT team FROM authuser WHERE email = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (email,))
        
        result = cursor.fetchone()
        if result:
            return result['team']  # Returns 'admin', 'instructor', or None
        return None  # User not found
    finally:
        conn.close()


async def fetch_types(team: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)

        if team in ["admin", "instructor"]:
            query = "SELECT DISTINCT type FROM session ORDER BY type ASC;"
        else:
            allowed_types = ("Resume Session", "Job Help", "Interview Prep", "Individual Mock", "Group Mock", "Misc")
            query = "SELECT DISTINCT type FROM session WHERE type IN (%s) ORDER BY type ASC;" % ", ".join(["%s"] * len(allowed_types))

        await loop.run_in_executor(None, cursor.execute, query, allowed_types if team not in ["admin", "instructor"] else ())
        types = cursor.fetchall()
        return types
    finally:
        conn.close()


async def fetch_sessions_by_type(course_id: int, session_type: str, team: str):
    if not course_id or not session_type:
        raise ValueError("Invalid course_id or session_type")

    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))

    try:
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT ns.*
            FROM session ns
            JOIN course_subject ncs 
            ON ns.subject_id = ncs.subject_id
            WHERE ns.subject_id != 0
            AND ncs.course_id IN (%s) 
            AND ns.type = %s 
            AND (ncs.course_id != 3 OR ns.sessiondate >= '2024-01-01')
            ORDER BY ns.sessiondate DESC;
        """

        if team not in ["admin", "instructor"]:
            allowed_types = ["Resume Session", "Job Help", "Interview Prep", "Individual Mock", "Group Mock", "Misc"]
            if session_type not in allowed_types:
                return []  # Return empty list if type not allowed for normal users

        await loop.run_in_executor(None, cursor.execute, query, (course_id, session_type))
        sessions = cursor.fetchall()
        return sessions
    finally:
        conn.close()


async def fetch_candidate_id_by_email(email: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id FROM candidate WHERE email = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (email,))
        result = cursor.fetchone()
        return result
    finally:
        conn.close()


async def user_contact(full_name: str, email: str = None, phone: str = None,  message: str = None):
    full_name = full_name.lower().strip() if full_name else None
    email = email.lower().strip() if email else None
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO whitebox_learning.lead (
                full_name,email, phone,notes) VALUES (%s, %s, %s, %s);
        """
        values = (
            full_name, email, phone,message)
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
        # cursor.execute("SELECT * FROM whitebox_learning.course_content")
        cursor.execute("SELECT Fundamentals, AIML FROM whitebox_learning.course_content")
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
        query = "UPDATE whitebox_learning.authuser SET passwd = %s WHERE uname = %s;"
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


async def fetch_recent_placements():
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, candidate_name, company, position, placement_date FROM recent_placements;"
        await loop.run_in_executor(None, cursor.execute, query)
        result = cursor.fetchall()

        # Convert placement_date to string
        for placement in result:
            if placement['placement_date']:
                placement['placement_date'] = placement['placement_date'].isoformat()

        return result
    finally:
        cursor.close()
        conn.close()


def normalize_interview(interview):
    if interview['interview_date']:
        interview['interview_date'] = interview['interview_date'].isoformat()
    if interview['interview_time']:
        if isinstance(interview['interview_time'], timedelta):
            total_seconds = int(interview['interview_time'].total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            interview['interview_time'] = (datetime.min + timedelta(hours=hours, minutes=minutes, seconds=seconds)).time()
        interview['interview_time'] = interview['interview_time'].isoformat()
    if interview['created_at']:
        interview['created_at'] = interview['created_at'].isoformat()
    return interview

async def run_query(query, params=None, fetch=False):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        await loop.run_in_executor(None, cursor.execute, query, params or ())
        result = cursor.fetchall() if fetch else None
        conn.commit()
        if fetch:
            result = [normalize_interview(row) for row in result]
        return result
    finally:
        cursor.close()
        conn.close()

async def fetch_recent_interviews(limit=10, offset=0):
    query = """
        SELECT * FROM recent_interviews
        ORDER BY id DESC
        LIMIT %s OFFSET %s;
    """
    return await run_query(query, params=(limit, offset), fetch=True)

async def fetch_interview_by_id(interview_id: int):
    query = """
        SELECT * FROM recent_interviews
        WHERE id = %s
        LIMIT 1;
    """
    result = await run_query(query, params=(interview_id,), fetch=True)
    return result[0] if result else None

async def fetch_interviews_by_name(name: str):
    query = """
        SELECT * FROM recent_interviews
        WHERE candidate_name LIKE %s
        ORDER BY interview_date DESC;
    """
    return await run_query(query, params=(f"%{name}%",), fetch=True)

async def insert_interview(data):
    query = """
        INSERT INTO recent_interviews (
            candidate_name, candidate_role, interview_time, interview_date,
            interview_mode, client_name, interview_location
        ) VALUES (%s, %s, %s, %s, %s, %s, %s);
    """
    params = (
        data.candidate_name, data.candidate_role, data.interview_time,
        data.interview_date, data.interview_mode, data.client_name,
        data.interview_location
    )
    await run_query(query, params=params)

async def delete_interview(interview_id: int):
    query = "DELETE FROM recent_interviews WHERE id = %s;"
    await run_query(query, params=(interview_id,))

async def update_interview(interview_id: int, data):
    query = """
        UPDATE recent_interviews
        SET candidate_name = %s,
            candidate_role = %s,
            interview_time = %s,
            interview_date = %s,
            interview_mode = %s,
            client_name = %s,
            interview_location = %s
        WHERE id = %s;
    """
    params = (
        data.candidate_name, data.candidate_role, data.interview_time,
        data.interview_date, data.interview_mode, data.client_name,
        data.interview_location, interview_id
    )
    return await run_query(query, params=params)


def get_user_by_username_sync(username: str):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM authuser WHERE uname = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

# .................................NEW INNOVAPTH......................................................
 
def get_db():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

async def fetch_candidates(filters: dict) -> List[Dict]:
    conn = None
    cursor = None
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        query = "SELECT * FROM candidate_marketing WHERE 1=1"
        params = []

        if filters.get("role"):
            query += " AND role = %s"
            params.append(filters["role"])
        if filters.get("experience"):
            query += " AND experience >= %s"
            params.append(int(filters["experience"]))
        if filters.get("location"):
            query += " AND location = %s"
            params.append(filters["location"])
        if filters.get("availability"):
            query += " AND availability = %s"
            params.append(filters["availability"])
        if filters.get("skills"):
            query += " AND skills LIKE %s"
            params.append(f"%{filters['skills']}%")

        cursor.execute(query, params)
        result = cursor.fetchall()
        return result
    except Error as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# .................................Unsubscribe Leads......................................................

def unsubscribe_lead_user(email: str) -> (bool, str):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT massemail_unsubscribe FROM `lead` WHERE email = %s", (email,))
        result = cursor.fetchone()

        if result is None:
            return False, "User not found"

        if result[0] == 1:
            return True, "Already unsubscribed"

        cursor.execute("UPDATE `lead` SET massemail_unsubscribe = %s WHERE email = %s", (1, email))
        conn.commit()

        return True, "Successfully unsubscribed"
    except Error as e:
        return False, "An error occurred"
    finally:
        cursor.close()
        conn.close()
