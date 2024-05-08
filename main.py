'''from fastapi import FastAPI
from fastapi import Request
import aiomysql

import mysql.connector

app = FastAPI()


db_config = {
    'host': '35.232.56.51',
    'user': 'whiteboxqa',
    'password': 'Innovapath1',
    'database': 'login',
}


# Dependency to get a database connection
def get_db():
    conn = mysql.connector.connect(**db_config)
    try:
        yield conn
    finally:
        conn.close()



def fetch_data_from_mysql():
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM login.login_details;")
        data = cursor.fetchall()
        return data
    finally:
        conn.close()

# Endpoint to get data from MySQL
@app.get("/data")
def get_data_from_mysql():
    data = fetch_data_from_mysql()
    return {"data": data}





def insert_data_into_mysql(Eid: int, Ename: str, Eemail: str, Edesignation: str, Eaddress: str):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO login_details (Eid, Ename, Eemail, Edesignation, Eaddress) VALUES (%s, %s, %s, %s, %s);", (Eid, Ename, Eemail, Edesignation, Eaddress))
        conn.commit()
    finally:
        conn.close()

@app.post("/post")
def insert_data_into_mysql(Eid: int, Ename: str, Eemail: str, Edesignation: str, Eaddress: str):
    insert_data_into_mysql(Eid, Ename, Eemail, Edesignation, Eaddress)
    return {"message": "User added successfully"}
'''


"""@app.post("/post")
async def add_user(request: Request):
    data = await request.json()
    Eid = data.get("Eid")
    Ename = data.get("Ename")
    Eemail = data.get("Eemail")
    Edesignation = data.get("Edesignation")
    Eaddress = data.get("Eaddress")

    if not all([Eid, Ename, Eemail, Edesignation, Eaddress]):
        return {"error": "All fields are required"}

    insert_data_into_mysql(Eid, Ename, Eemail, Edesignation, Eaddress)
    return {"message": "User added successfully"}"""





from fastapi import FastAPI, HTTPException
import mysql.connector

app = FastAPI()

db_config = {
    'host': '35.232.56.51',
    'user': 'whiteboxqa',
    'password': 'Innovapath1',
    'database': 'login',  # Database name is 'login'
}

# Dependency to get a database connection
def get_db():
    conn = mysql.connector.connect(**db_config)
    try:
        yield conn
    finally:
        conn.close()

def fetch_employees():
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM login.login_details;")
        data = cursor.fetchall()
        return data
    finally:
        conn.close()

def insert_employee(Eid: int, Ename: str, Eemail: str, Edesignation: str, Eaddress: str):
    conn = mysql.connector.connect(**db_config)
    try:
        print("hello")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO login.login_details (Eid, Ename, Eemail,Edesignation,Eaddress) VALUES (?,?,?,?,?);", (Eid, Ename, Eemail,Edesignation,Eaddress))
        conn.commit()
        return {"message": "Employee inserted successfully"}

    except mysql.connector.Error as e:
        return {"error": f"Error inserting employee: {e}"}
    finally:
        conn.close()

def update_employee(Eid: int, Ename: str, Eemail: str, Edesignation: str, Eaddress: str):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE login.login_details SET Ename = %s, Eemail = %s WHERE Eid = %s;", (Ename, Eemail, Eid,Edesignation,Eaddress))
        conn.commit()
        return {"message": "Employee updated successfully"}
    finally:
        conn.close()

def delete_employee(Eid: int):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login.login_details WHERE Eid = %s;", (Eid,))
        conn.commit()
        return {"message": "Employee deleted successfully"}
    finally:
        conn.close()

# Endpoint to get all employees
@app.get("/employeeget")
def get_employees():
    employees = fetch_employees()
    return {"employees": employees}

# Endpoint to insert an employee
@app.post("/employeepost")
def insert_employee(Eid: int, Ename: str, Eemail: str,Edesignation: str, Eaddress: str):
    return insert_employee(Eid, Ename, Eemail,Edesignation, Eaddress)

# Endpoint to update an employee
@app.put("/employeeput/{Eid}")
def update_an_employee(Eid: int, Ename: str, Eemail: str,Edesignation: str, Eaddress: str):
    return update_employee(Eid, Ename, Eemail,Edesignation, Eaddress)

# Endpoint to delete an employee
@app.delete("/employeedelete/{Eid}")
def delete_an_employee(Eid: int):
    return delete_employee(Eid)
