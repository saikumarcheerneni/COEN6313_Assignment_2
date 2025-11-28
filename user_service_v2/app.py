from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient
import pika, json, os

# ------------------ CONFIG ------------------

MONGO_URI = os.environ.get("USER_MONGO_URI", "mongodb://mongo_user:27017/")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client.userdb
users = db.users

app = FastAPI(
    title="User Service V2",
    description="User CRUD with validation + RabbitMQ sync events",
    version="2.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ MODELS ------------------

class User(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    address: str = Field(..., min_length=5)

class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    address: str | None = Field(None, min_length=5)

# ------------------ RABBITMQ EVENT ------------------

def publish_event(payload: dict):
    params = pika.ConnectionParameters(host=RABBITMQ_HOST)
    connection = pika.BlockingConnection(params)
    ch = connection.channel()
    ch.queue_declare(queue='sync_queue', durable=True)

    ch.basic_publish(
        exchange="",
        routing_key="sync_queue",
        body=json.dumps(payload),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    connection.close()

# ------------------ ROUTES ------------------

@app.get("/health")
def health():
    return {"status": "ok", "component": "user_v2"}

@app.post("/user")
def create_user(user: User):
    # Upsert OK for creation
    users.update_one({"user_id": user.user_id}, {"$set": user.dict()}, upsert=True)
    return {"message": "User created/updated", "user": user}


@app.put("/user/{user_id}")
def update_user(user_id: str, update: UserUpdate):

    # 1️⃣ Confirm user exists
    existing_user = users.find_one({"user_id": user_id})
    if not existing_user:
        raise HTTPException(status_code=404, detail="User does not exist")

    # 2️⃣ Prepare update fields
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    # 3️⃣ Update user db
    users.update_one({"user_id": user_id}, {"$set": update_data})

    # 4️⃣ Prepare event
    event_data = {f: update_data[f] for f in ["email", "address"] if f in update_data}

    # 5️⃣ Publish event for syncing orders
    if event_data:
        payload = {"user_id": user_id, "update": event_data}
        try:
            publish_event(payload)
        except Exception as e:
            return {
                "message": "User updated but sync event failed",
                "error": str(e)
            }

    return {
        "message": "User updated",
        "sync_event_sent": bool(event_data)
    }


@app.get("/user/{user_id}")
def get_user(user_id: str):
    user = users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
