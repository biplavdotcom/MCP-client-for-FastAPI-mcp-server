from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
mongo_uri = os.environ.get("MONGO_DB_URL")
try:
    client = MongoClient(mongo_uri)
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    sys.exit(1)
db = client["mcp-server"]

user_collection = db["users"]
project_collection = db["projects"]
