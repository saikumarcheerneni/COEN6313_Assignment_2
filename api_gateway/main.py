import json
import os
import random
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI(
    title="API Gateway",
    description="Routes requests to User Service v1/v2 and Order Service",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = os.environ.get("GATEWAY_CONFIG", "config.json")

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {"P": 0.5}

def choose_user_service():
    cfg = load_config()
    P = float(cfg.get("P", 0.5))
    return "http://user_v1:5001" if random.random() < P else "http://user_v2:5003"

ORDER_BASE = "http://order_service:5002"

# --------------- UTILITY: FORWARD REQUEST -------------------

sync def forward_request(request: Request, url: str):
    try:
        body = await request.json()
    except:
        body = None

    headers = dict(request.headers)
    headers.pop("host", None)

    response = httpx.request(
        method=request.method,
        url=url,
        json=body,
        headers=headers
    )
    return JSONResponse(status_code=response.status_code, content=response.json())

# ---------------------- ROUTES ----------------------

@app.get("/health")
def health():
    return {"status": "ok", "component": "gateway"}

@app.post("/user")
async def create_user(request: Request):
    return await forward_request(request, choose_user_service())

@app.get("/user/{subpath:path}")
@app.put("/user/{subpath:path}")
async def user_proxy(subpath: str, request: Request):
    return await forward_request(request, choose_user_service())

@app.get("/orders/{subpath:path}")
@app.get("/order/{subpath:path}")
@app.post("/order")
@app.put("/order/{subpath:path}")
async def order_proxy(subpath: str = "", request: Request = None):
    return await forward_request(request, ORDER_BASE)
