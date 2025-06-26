from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from models import user

app = FastAPI()

users = []

@app.post("/signup", operation_id="signup")
async def signup(username: str, password: str, email: str):
    new_user = user.User(username=username, password=password, email=email)
    users.append(new_user)
    return {"message": "User signed up successfully"}

@app.post("/login", operation_id="login")
async def login(username: str, password: str):
    for user in users:
        if user.username == username and user.password == password:
            return {"message": "User logged in successfully"}
        elif user.password != password:
            return {"message": "Invalid password"}
    return {"message": "Invalid username or password"}

@app.get("/clear_users", operation_id="clear_users")
async def clear_users():
    users.clear()
    return {"message": "Users cleared successfully"}

@app.get("/users", operation_id="get_users")
async def get_users():
    # return [{"username": user.username, "password": user.password, "email": user.email} for user in users]
    return users

mcp = FastApiMCP(app)
mcp.mount()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

