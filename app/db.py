import mysql.connector

db_config = {
    'host': '35.232.56.51',
    'user': 'whiteboxqa',
    'password': 'Innovapath1',
    'database': 'login',  # Database name is 'login'
}

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
        cursor = conn.cursor()
        cursor.execute("INSERT INTO login.login_details (Eid, Ename, Eemail, Edesignation, Eaddress) VALUES (%s, %s, %s, %s, %s);", (Eid, Ename, Eemail, Edesignation, Eaddress))
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
        cursor.execute("UPDATE login.login_details SET Ename = %s, Eemail = %s, Edesignation = %s, Eaddress = %s WHERE Eid = %s;", (Ename, Eemail, Edesignation, Eaddress, Eid))
        conn.commit()
        return {"message": "Employee updated successfully"}
    except mysql.connector.Error as e:
        return {"error": f"Error updating employee: {e}"}
    finally:
        conn.close()

def delete_employee(Eid: int):
    conn = mysql.connector.connect(**db_config)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM login.login_details WHERE Eid = %s;", (Eid,))
        conn.commit()
        return {"message": "Employee deleted successfully"}
    except mysql.connector.Error as e:
        return {"error": f"Error deleting employee: {e}"}
    finally:
        conn.close()
