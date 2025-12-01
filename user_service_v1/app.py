from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("USER_MONGO_URI", "mongodb://mongo_user:27017/")
client = MongoClient(MONGO_URI)
db = client.userdb
users = db.users

app = FastAPI(
    title="User Service V1",
    description="Basic user CRUD (no event publishing)",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class User(BaseModel):
    user_id: str
    name: str
    email: str
    address: str

class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    address: str | None = None

@app.get("/health")
def health():
    return {"status": "ok", "component": "user_v1"}

@app.post("/user")
def create_user(user: User):
    users.update_one({"user_id": user.user_id}, {"$set": user.dict()}, upsert=True)
    return {"message": "User created/updated", "user": user}

@app.put("/user/{user_id}")
def update_user(user_id: str, update: UserUpdate):
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data")
    users.update_one({"user_id": user_id}, {"$set": update_data}, upsert=True)
    return {"message": "User updated", "updated_fields": update_data}

@app.get("/user/{user_id}")
def get_user(user_id: str):
    user = users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user