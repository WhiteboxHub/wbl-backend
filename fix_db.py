import pymysql
conn = pymysql.connect(host='127.0.0.1', user='root', password='Swetha@123', port=3306)
cursor = conn.cursor()
cursor.execute("CREATE USER IF NOT EXISTS 'whitebox-db'@'%' IDENTIFIED BY 'password';")
cursor.execute("GRANT ALL PRIVILEGES ON *.* TO 'whitebox-db'@'%';")
cursor.execute("FLUSH PRIVILEGES;")
conn.commit()
conn.close()
print('Fixed definer issue.')
