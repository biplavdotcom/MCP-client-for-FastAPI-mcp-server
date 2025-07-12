from fastapi import FastAPI, HTTPException, WebSocket, Depends, status
from typing import Annotated
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi_mcp import FastApiMCP
from signup_login.models import user
from signup_login.core.db import user_collection, project_collection
# from client.client_gemini import run_mcp, MCPClient
import asyncio
from contextlib import asynccontextmanager
from typing import Dict
import pika
import bcrypt
import os
from signup_login.auth.auth import oauth2_scheme, verify_password, password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user, authenticate_user
from datetime import timedelta



_last_login_creds: Dict[str, str] = {}
_last_signup_creds: Dict[str, str] = {}
_project_info: Dict[str, str] = {}

app = FastAPI()


@app.post("/signup", status_code = status.HTTP_201_CREATED, operation_id="signup")
async def signup(name: str, email: str, password: str, re_password: str):
    if password != re_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    existing_user = user_collection.find_one({"email": email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user_collection.insert_one({"name": name, "email": email, "password": password_hash(password)})
    return {"message": "User signed up successfully"}

# @app.post("/login", operation_id="login")
# async def login(email: str, password: str):
#     user = user_collection.find_one({"email" : email})
#     if not user or not verify_password(password, user["password"]):
#         raise HTTPException(status_code=401, detail="Invalid email or password")
#     return {"message": "User logged in successfully"}

@app.post("/token", operation_id="login")
async def login_for_access_token(email: str, password: str):
    user_data = authenticate_user(email, password)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(user_data["email"], expires_delta=access_token_expires)
    return user.Token(access_token=access_token, token_type="bearer")
    # return "Logged In"

@app.get("/users/me", operation_id="get_current_user")
async def read_users_me(current_user: Annotated[dict, Depends(get_current_user)]):
    current_user.pop("password", None)  # Remove password before returning
    return current_user

@app.get("/clear_users", operation_id="clear_users")
async def clear_users():
    user_collection.delete_many({})
    return {"message": "Users cleared successfully"}

@app.get("/users", operation_id="get_users")
async def get_users():
    users = list(user_collection.find({}, {"_id": 0}))
    return users

@app.post("/create-project", operation_id="create_project")
async def create_project(project: user.Project, current_user: Annotated[dict, Depends(get_current_user)]):
    global _project_info
    _project_info = project.model_dump()
    _project_info["user_email"] = current_user["email"]
    project_collection.insert_one(project.model_dump())
    return {"message": "Project created successfully"}



mcp = FastApiMCP(app)
mcp.mount()

@app.post("/creds_signup")
async def put_signup_creds(creds: dict):
    required_fields = ["name", "email", "password", "re_password"]
    if not all(field in creds for field in required_fields):
        raise HTTPException(status_code=400, detail="Missing required fields")
    if creds["password"] != creds["re_password"]:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    global _last_signup_creds
    _last_signup_creds = creds
    return {"message": "Signup credentials pushed successfully"}

@app.post("/creds_login")
async def put_login_creds(creds: dict):
    required_fields = ["email", "password"]
    if not all(field in creds for field in required_fields):
        raise HTTPException(status_code=400, detail="Missing required fields")
    global _last_login_creds
    _last_login_creds = creds
    return {"message": "Credentials pushed successfully"}

@app.get("/creds_signup")
async def get_signup_creds():
    return _last_signup_creds or {}

@app.get("/creds_login")
async def get_login_creds():
    return _last_login_creds or {}

@app.get("/creds_project")
async def get_project_info():
    return _project_info or {}

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws/tool_args");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""
@app.get("/")
async def get(token: Annotated[str, Depends(oauth2_scheme)]):
    return HTMLResponse(html)

@app.websocket("/ws/tool_args")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        channel = connection.channel()
        messages = []
        
        def callback(ch, method, properties, body):
            messages.append(body)
            print(" [x] Received %r" % body)
        print(messages)
        channel.queue_declare(queue="tool_args")
        channel.basic_consume(queue="tool_args", on_message_callback=callback, auto_ack=True)
        channel.start_consuming()
        await websocket.send_text(messages[-1].decode("utf-8"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

