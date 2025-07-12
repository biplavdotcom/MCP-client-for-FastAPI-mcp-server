# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
import bcrypt
import jwt
from signup_login.core.db import user_collection
from jwt.exceptions import InvalidTokenError, PyJWTError as JWTError
from datetime import datetime, timedelta, timezone
from signup_login.models.user import UserInDB
from fastapi import Depends, HTTPException, status
from typing import Annotated
import os
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

# oauth2_scheme = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def password_hash(password: str):
    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return hashed_pw

def get_user(email: str):
    user = user_collection.find_one({"email" : email})
    if not user :
        return False
    return UserInDB(**user)

def authenticate_user(email: str, password: str):
    user = user_collection.find_one({"email" : email})
    if not user :
        return False
    if not verify_password(password, user["password"]):
        return False
    return user

def create_access_token(email: str, expires_delta: timedelta | None = None):

    to_encode = {"sub": email}
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception
        user_data = user_collection.find_one({"email": email}, {"_id": 0})
        if not user_data:
            raise credentials_exception
        return user_data
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise credentials_exception
    except Exception as e:
        print(f"Other error: {e}")
        raise credentials_exception

# async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)):
#     token = credentials.credentials
#     print("Received token:", token)
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         print("Decoded payload:", payload)
#     except jwt.ExpiredSignatureError:
#         print("Token expired")
#         raise HTTPException(status_code=401, detail="Token expired")
#     except jwt.InvalidTokenError:
#         print("Invalid token")
#         raise HTTPException(status_code=401, detail="Invalid token")
#     except Exception as e:
#         print("Other JWT error:", e)
#         raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
#     email = payload.get("sub")
#     print("Email from token:", email)
#     if not email:
#         raise HTTPException(status_code=401, detail="Invalid token payload")
    
#     user = user_collection.find_one({"email": email})
#     print("User found in DB:", user)
#     if not user:
#         raise HTTPException(status_code=401, detail="User not found")
    
#     return user

# async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> dict:
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Invalid authentication credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     token = credentials.credentials
#     print(f"Token received: {token}")
#     print(f"SECRET_KEY: {SECRET_KEY}")
#     print(f"ALGORITHM: {ALGORITHM}")
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         print(f"Payload: {payload}")
#         email: str = payload.get("sub")
#         if not email:
#             raise credentials_exception
#         user = user_collection.find_one({"email": email}, {"_id": 0})
#         if not user:
#             raise credentials_exception
#         return user
#     except JWTError as e:
#         print(f"JWT Error: {e}")
#         raise credentials_exception
#     except Exception as e:
#         print(f"Other error: {e}")
#         raise credentials_exception