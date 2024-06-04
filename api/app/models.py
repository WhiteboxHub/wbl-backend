from pydantic import BaseModel

class EmployeePost(BaseModel):
    Eid: int
    Ename: str
    Eemail: str = None
    Edesignation: str = None
    Eaddress: str = None
