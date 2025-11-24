# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from pymongo import MongoClient
# import os

# MONGO_URI = os.environ.get("ORDER_MONGO_URI", "mongodb://mongo_order:27017/")
# client = MongoClient(MONGO_URI)
# db = client.orderdb
# orders = db.orders

# app = FastAPI(
#     title="Order Service",
#     description="Handles creation and management of orders.",
#     version="1.0.0"
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ---------------- MODELS ----------------

# class Order(BaseModel):
#     order_id: str
#     user_id: str
#     items: list
#     status: str
#     email: str
#     address: str

# class OrderUpdate(BaseModel):
#     items: list | None = None
#     status: str | None = None
#     email: str | None = None
#     address: str | None = None

# # ---------------- ROUTES ----------------

# @app.get("/health")
# def health():
#     return {"status": "ok", "component": "order_service"}

# @app.post("/order")
# def create_order(order: Order):
#     orders.update_one(
#         {"order_id": order.order_id},
#         {"$set": order.dict()},
#         upsert=True
#     )
#     return {"message": "Order created/updated", "order": order}

# @app.get("/orders/{status}")
# def get_orders(status: str):
#     result = list(orders.find({"status": status}, {"_id": 0}))
#     return {"orders": result}

# @app.put("/order/{order_id}")
# def update_order(order_id: str, update: OrderUpdate):
#     update_data = {k: v for k, v in update.dict().items() if v is not None}

#     if not update_data:
#         raise HTTPException(status_code=400, detail="No fields to update")

#     orders.update_one({"order_id": order_id}, {"$set": update_data}, upsert=True)

#     return {"message": "Order updated", "updated_fields": update_data}
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("ORDER_MONGO_URI", "mongodb://mongo_order:27017/")
client = MongoClient(MONGO_URI)
db = client.orderdb
orders = db.orders

app = FastAPI(
    title="Order Service",
    description="Handles creation and management of orders with synchronization support.",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- MODELS ----------------

class Order(BaseModel):
    order_id: str
    user_id: str
    items: list
    status: str
    email: str
    address: str = Field(..., min_length=5)

class OrderUpdate(BaseModel):
    items: list | None = None
    status: str | None = None
    email: str | None = None
    address: str | None = Field(None, min_length=5)

# ---------------- ROUTES ----------------

@app.get("/health")
def health():
    return {"status": "ok", "component": "order_service"}


# ---------------- CREATE ORDER ----------------
@app.post("/order")
def create_order(order: Order):
    orders.update_one(
        {"order_id": order.order_id},
        {"$set": order.dict()},
        upsert=True
    )
    return {"message": "Order created/updated", "order": order}


# ---------------- GET ORDERS BY STATUS ----------------
@app.get("/orders/{status}")
def get_orders(status: str):
    result = list(orders.find({"status": status}, {"_id": 0}))
    return {"orders": result}


# ---------------- UPDATE ORDER ----------------
@app.put("/order/{order_id}")
def update_order(order_id: str, update: OrderUpdate):
    update_data = {k: v for k, v in update.dict().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = orders.update_one({"order_id": order_id}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")

    return {"message": "Order updated", "updated_fields": update_data}


# -------------- SYNC USER DETAILS (called by User Service) --------------
@app.put("/sync_user/{user_id}")
def sync_user(user_id: str, update: dict):
    """
    This endpoint is called by User Service whenever a user's email/address changes.
    It updates *all orders* belonging to that user.
    """

    valid_fields = {}
    if "email" in update and update["email"]:
        valid_fields["email"] = update["email"]

    if "address" in update and update["address"]:
        valid_fields["address"] = update["address"]

    if not valid_fields:
        raise HTTPException(status_code=400, detail="No valid fields to synchronize")

    # Update ALL orders for this user_id
    orders.update_many({"user_id": user_id}, {"$set": valid_fields})

    return {
        "message": "User info synchronized across orders",
        "updated_fields": valid_fields
    }
