from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from models import user
from core.db import collection

app = FastAPI()

@app.post("/signup", operation_id="signup")
async def signup(username: str, password: str, email: str):
    collection.insert_one({"username": username, "password": password, "email": email})
    return {"message": "User signed up successfully"}

@app.post("/login", operation_id="login")
async def login(username: str, password: str):
    user = collection.find_one({"username" : username})
    if user and user["password"] == password:
        return {"message": "User logged in successfully"}
    return {"message": "Invalid username or password"}

@app.get("/clear_users", operation_id="clear_users")
async def clear_users():
    collection.delete_many({})
    return {"message": "Users cleared successfully"}

@app.get("/users", operation_id="get_users")
async def get_users():
    users = list(collection.find({}, {"_id": 0}))
    return users

mcp = FastApiMCP(app)
mcp.mount()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

