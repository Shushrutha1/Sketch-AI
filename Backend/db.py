import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/sketch_ai")
client = MongoClient(MONGO_URI)
db = client.get_default_database()

# Initialize strict production indexing structures
db.users.create_index("username", unique=True)
db.users.create_index("email", unique=True)
db.leaderboard.create_index([("score", -1)])