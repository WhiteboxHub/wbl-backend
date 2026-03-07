import mysql.connector

def check_db():
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="root",
            database="local_host"
        )
        cursor = conn.cursor(dictionary=True)

        user_email = "sairam818595@gmail.com"
        print(f"Checking for user: {user_email}")
        
        cursor.execute("SELECT * FROM authuser WHERE uname = %s", (user_email,))
        user = cursor.fetchone()
        
        if user:
            print("--- User found in authuser ---")
            print(f"Username: {user['uname']}")
            print(f"Status: {user['status']}")
            print(f"Password hash in DB: {user['passwd']}")
            
            import hashlib
            calculated_md5 = hashlib.md5('Innovapath@1'.encode()).hexdigest()
            print(f"Calculated MD5 for 'Innovapath@1': {calculated_md5}")
            if user['passwd'] == calculated_md5:
                print("PASSWORDS MATCH!")
            else:
                print("PASSWORDS DO NOT MATCH!")
        else:
            print("--- User NOT found in authuser table ---")
        
        cursor.execute("SELECT * FROM employee WHERE email = %s", (user_email,))
        emp = cursor.fetchone()
        if emp:
            print("--- User found in employee table ---")
            print(f"Role/Status or anything for employee: {emp.get('status')}")
        else:
            print("--- User NOT found in employee table ---")
            
    except Exception as e:
        print(f"Error querying db: {e}")

if __name__ == "__main__":
    check_db()
