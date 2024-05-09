
from fastapi import FastAPI, HTTPException
from app.models import EmployeePost
from app.db import fetch_employees, insert_employee, update_employee, delete_employee

app = FastAPI()

@app.get("/employees")
def get_employees():
    employees = fetch_employees()
    return {"employees": employees}

@app.post("/employees/post")
def create_employee(details: EmployeePost):
    return insert_employee(details.Eid, details.Ename, details.Eemail, details.Edesignation, details.Eaddress)

@app.put("/employees/put/{Eid}")
def update_an_employee(Eid: int, details: EmployeePost):
    return update_employee(Eid, details.Ename, details.Eemail, details.Edesignation, details.Eaddress)

@app.delete("/employees/delete/{Eid}")
def delete_an_employee(Eid: int):
    return delete_employee(Eid)

















