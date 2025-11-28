import json
import os
import random
import httpx
from fastapi import FastAPI, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------

app = FastAPI(
    title="API Gateway",
    description="Routes requests to User Service v1/v2 and Order Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = os.environ.get("GATEWAY_CONFIG", "config.json")


def load_config():
    """Load strangler P value from config.json."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"P": 0.5}


def choose_user_service():
    """Select user_v1 or user_v2 based on probability P."""
    cfg = load_config()
    P = float(cfg.get("P", 0.5))
    return "http://user_v1:5001" if random.random() < P else "http://user_v2:5003"


ORDER_BASE = "http://order_service:5002"


# -------------------------------------------------------
# REQUEST MODELS FOR SWAGGER UI
# -------------------------------------------------------

class UserCreate(BaseModel):
    email: str
    address: str


class UserUpdate(BaseModel):
    email: str | None = None
    address: str | None = None


class OrderCreate(BaseModel):
    email: str
    address: str
    items: list[str]


class OrderStatusUpdate(BaseModel):
    status: str


# -------------------------------------------------------
# HELPER FUNCTION TO FORWARD REQUEST
# -------------------------------------------------------

async def forward(method: str, url: str, body=None):
    """Forward HTTP request to microservices."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, json=body)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    # Try JSON response, fallback to plain text
    try:
        return JSONResponse(status_code=response.status_code, content=response.json())
    except Exception:
        return JSONResponse(status_code=response.status_code, content={"message": response.text})


# -------------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "component": "gateway"}


# -------------------------------------------------------
# USER ROUTES
# -------------------------------------------------------

@app.post("/user")
async def create_user(data: UserCreate):
    """Create a user → forwarded to v1 or v2 based on P."""
    target = choose_user_service() + "/user"
    return await forward("POST", target, data.dict())


@app.put("/user/{user_id}")
async def update_user(user_id: str, data: UserUpdate):
    """Update user → forwarded to v1 or v2."""
    target = f"{choose_user_service()}/user/{user_id}"
    return await forward("PUT", target, data.dict())


@app.get("/user/{user_id}")
async def get_user(user_id: str):
    """GET user → routed to one version."""
    target = f"{choose_user_service()}/user/{user_id}"
    return await forward("GET", target)


# -------------------------------------------------------
# ORDER ROUTES
# -------------------------------------------------------

@app.post("/order")
async def create_order(data: OrderCreate):
    """Create order."""
    target = ORDER_BASE + "/order"
    return await forward("POST", target, data.dict())


@app.put("/order/{order_id}")
async def update_order(order_id: str, data: OrderStatusUpdate):
    target = f"{ORDER_BASE}/order/{order_id}"
    return await forward("PUT", target, data.dict())


@app.get("/order/{order_id}")
async def get_order(order_id: str):
    target = f"{ORDER_BASE}/order/{order_id}"
    return await forward("GET", target)
