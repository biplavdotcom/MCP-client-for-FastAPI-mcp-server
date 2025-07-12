from pydantic import BaseModel

class Signup(BaseModel):
    name: str
    password: str
    email: str

class Login(BaseModel):
    email: str
    password: str

class UserInDB(Signup):
    hashed_password: str

class Project(BaseModel):
    project_name: str
    project_description: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None