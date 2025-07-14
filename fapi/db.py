# from utils import md5_hash,verify_md5_hash,hash_password
# import mysql.connector
# from fastapi import HTTPException, status
# from mysql.connector import Error
# import os
# from typing import Optional,Dict
# import asyncio
# from dotenv import load_dotenv


# load_dotenv()

# db_config = {
#     'host': os.getenv('DB_HOST'),
#     'user': os.getenv('DB_USER'),
#     'password': os.getenv('DB_PASSWORD'),
#     'database': os.getenv('DB_NAME'),
#     'port': os.getenv('DB_PORT')
# }

# # ------------------------------------------------------------------------------------
# # async def insert_user_db(email: str, name: str, google_id: str):
# #     loop = asyncio.get_event_loop()
# #     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
# #     try:
# #         cursor = conn.cursor()
# #         query = "INSERT INTO authuser (uname, fullname, googleId, status) VALUES (%s, %s, %s, 'inactive');"
# #         await loop.run_in_executor(None, cursor.execute, query, (email, name, google_id))
# #         conn.commit()
# #     except Error as e:
# #         conn.rollback()
# #         print(f"Error inserting user: {e}")
# #         raise HTTPException(status_code=500, detail="Error inserting user")
# #     finally:
# #         cursor.close()
# #         conn.close() 
        
# async def insert_google_user_db(email: str, name: str, google_id: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()

#         # Insert user into authuser table
#         query1 = """
#             INSERT INTO authuser (uname, fullname, googleId, status, dailypwd, team, level, 
#             instructor, override, lastlogin, logincount, phone, address, city, Zip, country, message, 
#             registereddate, level3date) 
#             VALUES (%s, %s, %s, 'inactive', NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
#         """
#         await loop.run_in_executor(None, cursor.execute, query1, (email, name, google_id))

#         # Insert into the candidate table (you can modify this based on your needs)
#         query2 = """
#             INSERT INTO candidate (name, email, status, course) 
#             VALUES (%s, %s, 'active', 'ML');
#         """
#         await loop.run_in_executor(None, cursor.execute, query2, (name, email))

#         conn.commit()
#     except Error as e:
#         conn.rollback()
#         print(f"Error inserting user: {e}")
#         raise HTTPException(status_code=500, detail="Error inserting user")
#     finally:
#         cursor.close()
#         conn.close()

# # async def get_user_by_email(email: str):
# #     try:
# #         # Establish connection
# #         conn = mysql.connector.connect(**db_config)
# #         if conn.is_connected():
# #             cursor = conn.cursor(dictionary=True)  # Use dictionary=True to get results as dictionaries
# #             query = "SELECT * FROM authuser WHERE uname = %s"
# #             cursor.execute(query, (email,))
# #             result = cursor.fetchone()
# #             return result
# #     except Error as e:
# #         # print(f"Error: {e}")
# #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# #     finally:
# #         if conn.is_connected():
# #             cursor.close()
# #             conn.close() 
            
# # Function to fetch user by email
# async def get_google_user_by_email(email: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT * FROM authuser WHERE uname = %s;"
#         await loop.run_in_executor(None, cursor.execute, query, (email,))
#         user = cursor.fetchone()
#         return user
#     except Exception as e:
#         print(f"Error fetching user: {e}")
#         raise HTTPException(status_code=500, detail="Error fetching Google  user")
#     finally:
#         cursor.close()
#         conn.close()
        
# # ------------------------------------------------------------------------------------
            

# # Async function to insert a user into the database
# async def insert_user(uname: str, passwd: str, dailypwd: Optional[str] = None, team: str = None, level: str = None, 
#                       instructor: str = None, override: str = None, status: str = None, lastlogin: str = None, 
#                       logincount: str = None, fullname: str = None, phone: str = None, address: str = None, 
#                       city: str = None, Zip: str = None, country: str = None, message: str = None, 
#                       registereddate: str = None, level3date: str = None, candidate_info: Dict[str, Optional[str]] = None):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
        
#         # Insert into authuser table
#         query1 = """
#             INSERT INTO whitebox_learning.authuser (
#                 uname, passwd, dailypwd, team, level, instructor, override, status, 
#                 lastlogin, logincount, fullname, phone, address, city, Zip, country, 
#                 message, registereddate, level3date
#             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
#         """
#         values1 = (
#             uname, passwd, dailypwd, team, level, instructor, override, status, 
#             lastlogin, logincount, fullname, phone, address, city, Zip, country, 
#             message, registereddate, level3date
#         )
#         await loop.run_in_executor(None, cursor.execute, query1, values1)
        
#         # Insert into candidate table
#         query2 = """
#             INSERT INTO whitebox_learning.candidate (
#                 name, enrolleddate, email, course, phone, status, address, city, country, zip
#             ) VALUES (%s, %s, %s, 'ML', %s,'active', %s, %s, %s, %s);
#         """
#         values2 = (
#             candidate_info['name'], candidate_info['enrolleddate'], candidate_info['email'],
#             candidate_info['phone'], candidate_info['address'], 
#             candidate_info['city'], candidate_info['country'], candidate_info['zip']
#         )
#         await loop.run_in_executor(None, cursor.execute, query2, values2)

#         #get the last inserted ID to for candidate_ID
#         candidate_id = cursor.lastrowid

#          ## Insert the candidate_id into the candidate_resume table
#         query3 = """
#             INSERT INTO whitebox_learning.candidate_resume (
#                 candidate_id
#             ) VALUES (%s);
#         """
#         values3 = (candidate_id,)
#         await loop.run_in_executor(None, cursor.execute, query3, values3)

#         conn.commit()
#     except Error as e:
#         # print(f"Error inserting user: {e}")
#         conn.rollback()
#         raise HTTPException(status_code=500, detail="Error inserting user")
#     finally:
#         cursor.close()
#         conn.close()



   
            
# async def get_user_by_username(uname: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT * FROM whitebox_learning.authuser WHERE uname = %s;"
#         await loop.run_in_executor(None, cursor.execute, query, (uname,))
#         result = cursor.fetchone()
#         return result
#     finally:
#         conn.close()   



# async def update_login_info(user_id: int):
#     loop = asyncio.get_event_loop()
#     conn = loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
#         query = """
#             UPDATE whitebox_learning.authuser 
#             SET lastlogin = NOW(), logincount = logincount + 1 
#             WHERE id = %s;
#         """
#         await loop.run_in_executor(None, cursor.execute, query, (user_id,))
#         conn.commit()
#     except Error as e:
#         # print(f"Error updating login info: {e}")
#         conn.rollback()
#         raise HTTPException(status_code=500, detail="Error updating login info")
#     finally:
#         cursor.close()
#         conn.close()

# async def insert_login_history(user_id: int, ipaddress: str, useragent: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
#         query = """
#             INSERT INTO whitebox_learning.loginhistory (loginid, logindatetime, ipaddress, useragent) 
#             VALUES (%s, NOW(), %s, %s);
#         """
#         await loop.run_in_executor(None, cursor.execute, query, (user_id, ipaddress, useragent))
#         conn.commit()
#     except Error as e:
#         # print(f"Error inserting login history: {e}")
#         conn.rollback()
#         raise HTTPException(status_code=500, detail="Error inserting login history")
#     finally:
#         cursor.close()
#         conn.close()
    

# #fucntion to merge batchs
# def merge_batches(q1_response,q2_response):
#     # Combine the two lists
#     all_batches = q1_response + q2_response    
#     seen_batches = set()
#     unique_batches = []


#     for batch in all_batches:
#         # print(batch['batchname'])
#         if batch['batchname'] not in seen_batches:
#             seen_batches.add(batch['batchname'])
#             unique_batches.append(batch)
#     # Sort unique_batches by batchname in descending order (latest to oldest)
#     unique_batches.sort(key=lambda x: x['batchname'], reverse=True)
#     return unique_batches

# #function to fetch batch names based on courses
# async def fetch_course_batches(subject:str=None):
#     loop = asyncio.get_event_loop()
#     conn = loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         batchquery = f"""
#                 SELECT batchname,batchid 
#                 FROM whiteboxqa.new_batch
#                 WHERE subject = '{subject}'
#                 GROUP BY batchname
#                 ORDER BY batchname DESC;
#                 """
#         await loop.run_in_executor(None, cursor.execute, batchquery)
#         r1 = cursor.fetchall()
#         return r1
#     except Error as e:
#         # print(f"Error: {e}")
#         return []
#     finally:
#         conn.close()


# async def fetch_subject_batch_recording(subject: str = None, batchid: int = None):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = f"""
#                 SELECT DISTINCT nr.id, nr.batchname, nr.description, nr.type, nr.classdate, nr.link, nr.videoid, nr.subject, nr.filename, nr.lastmoddatetime, nr.new_subject_id
#                 FROM recording nr
#                 JOIN recording_batch rb ON nr.id = rb.recording_id
#                 JOIN new_batch b ON rb.batch_id = b.batchid
#                 JOIN course_subject ncs ON b.courseid = ncs.course_id
#                 JOIN course nc ON ncs.course_id = nc.id
#                 WHERE nc.alias = '{subject}'
#                 AND b.batchid = {batchid}
#                 AND nr.new_subject_id IN (
#                 SELECT subject_id
#                 FROM course_subject
#                 WHERE course_id = (
#                 SELECT id
#                 FROM course
#                 WHERE alias = '{subject}'
#                 )
#                 );
#                 """
#         await loop.run_in_executor(None, cursor.execute, query)
#         recordings = cursor.fetchall()
#         return recordings
#     finally:
#         conn.close()


# async def fetch_keyword_recordings(subject: str, keyword: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = """                
#                 SELECT DISTINCT nr.id,nr.batchname, nr.description, nr.type,nr.classdate, nr.link, nr.videoid, nr.subject, nr.filename, nr.lastmoddatetime, nr.new_subject_id
#                 FROM recording nr
#                 JOIN subject ns ON nr.new_subject_id = ns.id
#                 JOIN course_subject ncs ON ns.id = ncs.subject_id
#                 JOIN course nc ON ncs.course_id = nc.id               
#                 WHERE nc.alias =%s
               	    
#                 AND nr.description LIKE %s
#                 ORDER BY nr.classdate DESC;               
#                 """
#         await loop.run_in_executor(None, cursor.execute, query, (subject, '%' + keyword + '%'))
#         recordings = cursor.fetchall()
#         return recordings
#     finally:
#         conn.close()

            
# async def fetch_keyword_presentation(search, course):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         type_mapping = {
#             "Presentations": "P",
#             "Cheatsheets": "C",
#             "Diagrams": "D",
#             "Installations": "I",
#             "Templates": "T",
#             "Books": "B",
#             "Softwares": "S",
#             "Newsletters": "N"
#         }
#         type_code = type_mapping.get(search)
#         if type_code:
#             query = """
#             SELECT * FROM whitebox_learning.course_material 
#             WHERE type = %s AND (courseid = 0 OR courseid = %s) ORDER BY name ASC;
#             """
#             courseid_mapping = {
#                 "QA": 1,
#                 "UI": 2,
#                 "ML": 4
#             }
#             selected_courseid = courseid_mapping.get(course.upper())

#             await loop.run_in_executor(None, cursor.execute, query, (type_code, selected_courseid))
#             data = cursor.fetchall()
#             return data
#         else:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Invalid search keyword. Please select one of: Presentations, Cheatsheets, Diagrams, Installations, Templates, Books, Softwares, Newsletters"
#             )
#     except mysql.connector.Error as err:
#         # print(f"Error: {err}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Database error occurred"
#         )
#     finally:
#         cursor.close()
#         conn.close()


# # async def get_user_by_username(uname: str):
# #     loop = asyncio.get_event_loop()
# #     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
# #     try:
# #         cursor = conn.cursor(dictionary=True)
# #         query = "SELECT * FROM whitebox_learning.authuser WHERE uname = %s;"
# #         await loop.run_in_executor(None, cursor.execute, query, (uname,))
# #         result = cursor.fetchone()
# #         return result
# #     finally:
# #         conn.close()


# async def fetch_candidate_id_by_email(email: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         query = "SELECT candidateid FROM candidate WHERE email = %s;"
#         await loop.run_in_executor(None, cursor.execute, query, (email,))
#         result = cursor.fetchone()
#         return result
#     finally:
#         conn.close()


# # Async function to fetch sessions by category
# async def fetch_sessions_by_type(category: str = None):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor(dictionary=True)
#         if category:
#             query = "SELECT  * FROM whitebox_learning.session WHERE type = %s ORDER BY sessiondate DESC;"
#             await loop.run_in_executor(None, cursor.execute, query, (category,))
#         else:
#             query = "SELECT *  FROM whitebox_learning.session ORDER BY type ASC;"
#             await loop.run_in_executor(None, cursor.execute, query)
#         sessions = cursor.fetchall()
#         return sessions
#     finally:
#         conn.close()
        

# async def user_contact(name: str, email: str = None, phone: str = None,  message: str = None):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
#         query = """
#             INSERT INTO whitebox_learning.leads (
#                 name,email, phone,notes) VALUES (%s, %s, %s, %s);
#         """
#         values = (
#             name, email, phone,message)
#         await loop.run_in_executor(None, cursor.execute, query, values)
#         conn.commit()
#     except Error as e:
#         # print(f"Error inserting user: {e}")
#         raise HTTPException(status_code=409, detail="Response already sent!")
#     finally:
#         cursor.close()
#         conn.close()

# def course_content():
#     conn = mysql.connector.connect(**db_config)
#     try:
#         cursor = conn.cursor(dictionary=True)  # Use dictionary=True to get rows as dictionaries
#         cursor.execute("SELECT * FROM whitebox_learning.course_content")
#         data = cursor.fetchall()
#         return data 
#     finally:
#         conn.close()


# def unsubscribe_user(email: str) -> (bool, str): # type: ignore
#     conn = mysql.connector.connect(**db_config)
#     try:
#         cursor = conn.cursor()
#         cursor.execute("SELECT remove FROM massemail WHERE email = %s", (email,))
#         result = cursor.fetchone()

#         if result is None:
#             return False, "User not found"

#         if result[0] == 'Y':
#             return True, "Already unsubscribed"

#         cursor.execute("UPDATE massemail SET remove = 'Y' WHERE email = %s", (email,))
#         conn.commit()

#         return True, "Successfully unsubscribed"
#     except Error as e:
#         # print(f"Error: {e}")
#         return False, "An error occurred"
#     finally:
#         cursor.close()
#         conn.close()
        
        
        
# async def update_user_password(uname: str, new_password: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
        
#         # Hash the new password
#         hashed_password = md5_hash(new_password)
        
#         # Update the user's password
#         query = "UPDATE whitebox_learning.authuser SET passwd = %s WHERE uname = %s;"
#         values = (hashed_password, uname)
        
#         await loop.run_in_executor(None, cursor.execute, query, values)
#         conn.commit()
        
#         if cursor.rowcount == 0:
#             raise HTTPException(status_code=404, detail="User not found")
#     except Error as e:
#         # print(f"Error updating password: {e}")
#         conn.rollback()
#         raise HTTPException(status_code=500, detail="Error updating password")
#     finally:
#         cursor.close()
#         conn.close()      
        
# # async def get_user_by_email(email: str):
# #     try:
# #         # Establish connection
# #         conn = mysql.connector.connect(**db_config)
# #         if conn.is_connected():
# #             cursor = conn.cursor(dictionary=True)  # Use dictionary=True to get results as dictionaries
# #             query = "SELECT * FROM authuser WHERE uname = %s"
# #             cursor.execute(query, (email,))
# #             result = cursor.fetchone()
# #             return result
# #     except Error as e:
# #         # print(f"Error: {e}")
# #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# #     finally:
# #         if conn.is_connected():
# #             cursor.close()
# #             conn.close()        

# async def update_user_password(email: str, new_password: str):
#     conn = mysql.connector.connect(**db_config)
#     try:
#         cursor = conn.cursor()
#         hashed_password = hash_password(new_password)
#         cursor.execute("UPDATE authuser SET passwd = %s WHERE uname = %s", (hashed_password, email))
#         conn.commit()
#     finally:
#         cursor.close()
#         conn.close()


# wbl-backend/fapi/db.py
from fapi.utils import md5_hash,verify_md5_hash,hash_password,verify_reset_token
import mysql.connector
from fastapi import HTTPException, status
from mysql.connector import Error
import os
from typing import Optional,Dict,List
import asyncio
from dotenv import load_dotenv
from datetime import date,datetime, time, timedelta  





load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'port': os.getenv('DB_PORT')
}

# ------------------------------------------------------------------------------------
# async def insert_user_db(email: str, name: str, google_id: str):
#     loop = asyncio.get_event_loop()
#     conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
#     try:
#         cursor = conn.cursor()
#         query = "INSERT INTO authuser (uname, fullname, googleId, status) VALUES (%s, %s, %s, 'inactive');"
#         await loop.run_in_executor(None, cursor.execute, query, (email, name, google_id))
#         conn.commit()
#     except Error as e:
#         conn.rollback()
#         print(f"Error inserting user: {e}")
#         raise HTTPException(status_code=500, detail="Error inserting user")
#     finally:
#         cursor.close()
#         conn.close() 
        
async def insert_google_user_db(email: str, name: str, google_id: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()

        # Insert user into authuser table
        query1 = """
            INSERT INTO authuser (uname, fullname, googleId, passwd, status,  dailypwd, team, level, 
            instructor, override, lastlogin, logincount, phone, address, city, Zip, country, message, 
            registereddate, level3date) 
            VALUES (%s, %s, %s, %s, 'inactive', NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
        """
        await loop.run_in_executor(None, cursor.execute, query1, (email, name, google_id, "google_dummy"))

        # Insert into the candidate table (you can modify this based on your needs)
        # query2 = """
        #     INSERT INTO candidate (name, email, status, course) 
        #     VALUES (%s, %s, 'active', 'ML');
        # """
        # await loop.run_in_executor(None, cursor.execute, query2, (name, email))

        conn.commit()
    except Error as e:
        conn.rollback()
        print(f"Error inserting user: {e}")
        raise HTTPException(status_code=500, detail="Error inserting user")
    finally:
        cursor.close()
        conn.close()

# async def get_user_by_email(email: str):
#     try:
#         # Establish connection
#         conn = mysql.connector.connect(**db_config)
#         if conn.is_connected():
#             cursor = conn.cursor(dictionary=True)  # Use dictionary=True to get results as dictionaries
#             query = "SELECT * FROM authuser WHERE uname = %s"
#             cursor.execute(query, (email,))
#             result = cursor.fetchone()
#             return result
#     except Error as e:
#         # print(f"Error: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#     finally:
#         if conn.is_connected():
#             cursor.close()
#             conn.close() 
            
# Function to fetch user by email
async def get_google_user_by_email(email: str):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM authuser WHERE uname = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (email,))
        user = cursor.fetchone()
        return user
    except Exception as e:
        print(f"Error fetching user: {e}")
        raise HTTPException(status_code=500, detail="Error fetching Google  user")
    finally:
        cursor.close()
        conn.close()
        

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
    visastatus: Optional[str] = None,
    registereddate: str = None,
    level3date: str = None,
    experience: Optional[str] = None,
    education: Optional[str] = None,
    specialization: Optional[str] = None,
    referred_by: Optional[str] = None,
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
                visastatus,experience, education, specialization, referred_by 

                message, registereddate, level3date
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, 'inactive',
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            );
        """

        values1 = (
            uname, passwd, dailypwd, team, level, instructor, override, 
            lastlogin, logincount, fullname, phone, address, city, Zip.lower() if Zip else None, country,
            visastatus, experience, education, referred_by,
            message, registereddate, level3date
        )

        await loop.run_in_executor(None, cursor.execute, query1, values1)
        
        # Insert into candidate table
        # query2 = """
        #     INSERT INTO wbl_newDB.candidate (
        #         name, enrolleddate, email, course, phone, status, address, city, country, zip
        #     ) VALUES (%s, %s, %s, 'ML', %s,'active', %s, %s, %s, %s);
        # """
        # values2 = (
        #     candidate_info['name'], candidate_info['enrolleddate'], candidate_info['email'],
        #     candidate_info['phone'], candidate_info['address'], 
        #     candidate_info['city'], candidate_info['country'], candidate_info['zip']
        # )
        # await loop.run_in_executor(None, cursor.execute, query2, values2)

        # get the last inserted ID to for candidate_ID
        # candidate_id = cursor.lastrowid

        #  # Insert the candidate_id into the candidate_resume table
        # query3 = """
        #     INSERT INTO wbl_newDB.candidate_resume (
        #         candidate_id
        #     ) VALUES (%s);
        # """
        # values3 = (candidate_id,)
        # await loop.run_in_executor(None, cursor.execute, query3, values3)



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


# import asyncio
# import mysql.connector

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


# -----------------------------------------------------------------

            
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
        query = "SELECT candidateid FROM candidate WHERE email = %s;"
        await loop.run_in_executor(None, cursor.execute, query, (email,))
        result = cursor.fetchone()
        return result
    finally:
        conn.close()





async def user_contact(name: str, email: str = None, phone: str = None,  message: str = None):
    loop = asyncio.get_event_loop()
    conn = await loop.run_in_executor(None, lambda: mysql.connector.connect(**db_config))
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO whitebox_learning.leads (
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


# ------------------------------------------ Avtar -------------------------
def get_user_by_username_sync(username: str):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM authuser WHERE uname = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def get_connection():
    try:
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            port=int(db_config['port']),
        )
        return conn
    except Error as e:
        print("Database connection error:", e)
        raise HTTPException(status_code=500, detail="Database connection failed")
    



def get_all_candidates_paginated(page: int = 1, limit: int = 100):
    from datetime import date, datetime
    offset = (page - 1) * limit

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # query = "SELECT * FROM candidate LIMIT %s OFFSET %s"
    query = "SELECT * FROM candidate ORDER BY candidateid DESC LIMIT %s OFFSET %s"
    cursor.execute(query, (limit, offset))
    rows = cursor.fetchall()

    for row in rows:
        for key in row:
            if isinstance(row[key], (date, datetime)):
                row[key] = row[key].isoformat()

    cursor.close()
    conn.close()
    return rows


def get_candidate_by_name(name: str):
    name = name.strip().lower()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        query = "SELECT * FROM candidate WHERE LOWER(name) LIKE %s"
        # cursor.execute(query, (name,))
        cursor.execute(query, (f"%{name}%",))
        rows = cursor.fetchall()

        for row in rows:
            for key in row:
                if isinstance(row[key], (date, datetime)):
                    row[key] = row[key].isoformat()

        return rows 

    finally:
        cursor.close()
        conn.close()


#Get Candidates status
def get_candidates_by_status(status: str, page: int = 1, limit: int = 100) -> List[dict]:
    offset = (page - 1) * limit

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT * FROM candidate
        WHERE LOWER(status) = %s
        ORDER BY candidateid DESC
        LIMIT %s OFFSET %s
    """
    cursor.execute(query, (status.lower(), limit, offset))
    rows = cursor.fetchall()

    # Convert date/datetime fields to ISO format
    for row in rows:
        for key, value in row.items():
            if isinstance(value, (date, datetime)):
                row[key] = value.isoformat()

    cursor.close()
    conn.close()
    return rows


def get_candidate_by_id(candidateid: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM candidate WHERE candidateid = %s", (candidateid,))
    row = cursor.fetchone()
    if row:
        for key in row:
            if isinstance(row[key], (date, datetime)):
                row[key] = row[key].isoformat()
    cursor.close()
    conn.close()
    return row


def create_candidate(candidate_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ", ".join(["%s"] * len(candidate_data))
    columns = ", ".join(candidate_data.keys())
    sql = f"INSERT INTO candidate ({columns}) VALUES ({placeholders})"
    cursor.execute(sql, list(candidate_data.values()))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id

def update_candidate(candidateid: int, candidate_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{key}=%s" for key in candidate_data.keys()])
    sql = f"UPDATE candidate SET {set_clause} WHERE candidateid=%s"
    values = list(candidate_data.values()) + [candidateid]
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()

def delete_candidate(candidateid: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM candidate WHERE candidateid = %s", (candidateid,))
    conn.commit()
    cursor.close()
    conn.close()




def serialize_rows(rows):
    for row in rows:
        for key in row:
            if isinstance(row[key], (date, datetime)):
                row[key] = row[key].isoformat()
    return rows


def get_all_placements(page: int = 1, limit: int = 100) -> List[dict]:
    offset = (page - 1) * limit
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM placement ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return serialize_rows(rows)


def get_placement_by_id(placement_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM placement WHERE id = %s", (placement_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return serialize_rows([row])[0] if row else None


def search_placements_by_candidate_name(name: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM placement WHERE LOWER(candidate_name) LIKE %s"
    cursor.execute(query, (f"%{name.strip().lower()}%",))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return serialize_rows(rows)


def create_placement(data: dict) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    query = f"INSERT INTO placement ({columns}) VALUES ({placeholders})"
    cursor.execute(query, list(data.values()))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def update_placement(placement_id: int, data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
    query = f"UPDATE placement SET {set_clause} WHERE id = %s"
    values = list(data.values()) + [placement_id]
    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()


def delete_placement(placement_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM placement WHERE id = %s", (placement_id,))
    conn.commit()
    cursor.close()
    conn.close()








def fetch_all_leads_paginated(page: int, limit: int):
    offset = (page - 1) * limit
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leads ORDER BY leadid DESC LIMIT %s OFFSET %s", (limit, offset))
    leads = cursor.fetchall()

    for lead in leads:
        closedate = lead.get("closedate")
        if isinstance(closedate, (date, datetime)):
            lead["closedate"] = closedate.isoformat()

    cursor.close()
    conn.close()
    return leads


def search_leads(name: Optional[str], email: Optional[str]):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if name:
        query += " AND name LIKE %s"
        params.append(f"%{name}%")
    if email:
        query += " AND email LIKE %s"
        params.append(f"%{email}%")

    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def fetch_lead_by_id(leadid: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leads WHERE leadid = %s", (leadid,))
    lead = cursor.fetchone()
    cursor.close()
    conn.close()
    return lead


def create_new_lead(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    keys = ", ".join(data.keys())
    values = tuple(data.values())
    placeholders = ", ".join(["%s"] * len(values))
    sql = f"INSERT INTO leads ({keys}) VALUES ({placeholders})"
    cursor.execute(sql, values)
    conn.commit()
    lead_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return lead_id

def update_existing_lead(leadid: int, data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join(f"{key} = %s" for key in data.keys())
    values = list(data.values()) + [leadid]
    sql = f"UPDATE leads SET {set_clause} WHERE leadid = %s"
    cursor.execute(sql, tuple(values))
    conn.commit()
    cursor.close()
    conn.close()

def delete_lead_by_id(leadid: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads WHERE leadid = %s", (leadid,))
    conn.commit()
    cursor.close()
    conn.close()