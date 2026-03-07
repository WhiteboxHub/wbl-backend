import mysql.connector
import json

try:
    conn = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="root",
        database="newschema"
    )
    cursor = conn.cursor(dictionary=True)
    
    # Check AutomationWorkflowORM
    cursor.execute("SELECT id, workflow_key, name, workflow_type, status, recipient_list_sql, credentials_list_sql FROM automation_workflows")
    workflows = cursor.fetchall()
    print("Workflows:")
    print(json.dumps(workflows, indent=2))
    
    # Check Hiring Cafe Jobs
    cursor.execute("SELECT id, title, company_name, source, source_uid, job_url FROM job_listing WHERE source = 'hiring.cafe' LIMIT 10")
    hiring_cafe_jobs = cursor.fetchall()
    print("\nHiring Cafe Jobs (Sample):")
    print(json.dumps(hiring_cafe_jobs, indent=2))
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
