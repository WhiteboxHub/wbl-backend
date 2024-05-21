from pydantic import BaseModel

class UserPost(BaseModel):
    username: str
    password: str
    email: str
    phone: int
    Zip: int
    address: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
