from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient
import os
import requests

MONGO_URI = os.environ.get("USER_MONGO_URI", "mongodb://mongo_user:27017/")
client = MongoClient(MONGO_URI)
db = client.userdb
users = db.users_v1

app = FastAPI(
    title="User Service V1",
    description="Basic user CRUD with synchronization support",
    version="1.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- MODELS --------------------

class User(BaseModel):
    user_id: str
    name: str
    email: EmailStr   # ✔ email validation
    address: str = Field(..., min_length=5)  # ✔ minimum address validation

class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    address: str | None = Field(None, min_length=5)

# -------------------- ROUTES --------------------

@app.get("/health")
def health():
    return {"status": "ok", "component": "user_v1"}


# -------------------- CREATE USER --------------------
@app.post("/user")
def create_user(user: User):
    users.update_one({"user_id": user.user_id}, {"$set": user.dict()}, upsert=True)
    return {"message": "User created/updated", "user": user}


# -------------------- UPDATE USER + SYNC --------------------
@app.put("/user/{user_id}")
def update_user(user_id: str, update: UserUpdate):

    # 1) Ensure user exists
    existing_user = users.find_one({"user_id": user_id})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User does not exist")

    # 2) Prepare update data
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update fields provided")

    # 3) Update user database
    users.update_one({"user_id": user_id}, {"$set": update_data})

    # 4) SYNC with Order Service
    ORDER_SERVICE_URL = "http://order_service:5002/sync_user"

    try:
        requests.put(f"{ORDER_SERVICE_URL}/{user_id}", json=update_data)
    except:
        # If order service is down, we still update user but warn
        return {
            "message": "User updated, but order service unreachable for synchronization",
            "updated_fields": update_data
        }

    return {
        "message": "User updated and synchronized",
        "updated_fields": update_data
    }


# -------------------- GET USER --------------------
@app.get("/user/{user_id}")
def get_user(user_id: str):
    user = users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
