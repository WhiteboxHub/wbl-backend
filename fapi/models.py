from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    uname: str
    passwd: str

class UserRegistration(BaseModel):
    uname: str
    passwd: str
    dailypwd: Optional[str] = None
    team: Optional[str] = None
    level: Optional[str] = None
    instructor: Optional[str] = None
    override: Optional[str] = None
    status: Optional[str] = None
    lastlogin: Optional[str] = None
    logincount: Optional[str] = None
    fullname: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    Zip: Optional[str] = None
    country: Optional[str] = None
    message: Optional[str] = None
    registereddate: Optional[str] = None
    level3date: Optional[str] = None
    last: Optional[str] = None
    
    
class ContactForm(BaseModel):
    name: str
    email: str
    phone: str
    message: str
    
    
    # uname: str
    # passwd: str
    # dailypwd: str=None 
    # team:str =None
    # level:str =None
    # instructor:str =None
    # override:str=None
    # status:str=None
    # lastlogin:str=None
    # logincount:str=None
    # fullname: str
    # phone: str
    # address: str
    # city:str
    # Zip:str
    # country:str
    # message:str
    # registereddate:str=None
    # level3date:str=None
    # last:str=None




class Token(BaseModel):
    access_token: str
    token_type: str
