# import pika, json, os, time, threading
# from pymongo import MongoClient
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# # ==== Environment Variables ====
# RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
# ORDER_MONGO_URI = os.environ.get("ORDER_MONGO_URI", "mongodb://mongo_order:27017/")

# # ==== FastAPI App ====
# app = FastAPI(
#     title="Event Sync Service",
#     description="This service syncs user updates to order database (RabbitMQ → MongoDB)",
#     version="1.0"
# )

# # Allow all origins (optional)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ==== MongoDB ====
# order_client = MongoClient(ORDER_MONGO_URI)
# order_db = order_client.orderdb
# orders = order_db.orders

# # Store last processed events for dashboard
# last_events = []

# # ==== RabbitMQ Consumer Function ====
# def rabbitmq_consumer():
#     print("=== [consumer] Starting Event Consumer ===")
#     print(f"[consumer] RabbitMQ host: {RABBITMQ_HOST}")
#     print(f"[consumer] Mongo URI: {ORDER_MONGO_URI}")

#     # Retry logic
#     connection = None
#     for attempt in range(10):
#         try:
#             print(f"[consumer] Attempting RabbitMQ connection ({attempt+1}/10)...")
#             params = pika.ConnectionParameters(host=RABBITMQ_HOST)
#             connection = pika.BlockingConnection(params)
#             print("[consumer] Connected to RabbitMQ!")
#             break
#         except Exception:
#             print("[consumer] RabbitMQ not ready, retrying in 5 seconds...")
#             time.sleep(5)

#     if not connection:
#         print("[consumer] FAILED to connect to RabbitMQ.")
#         return

#     channel = connection.channel()
#     channel.queue_declare(queue="sync_queue", durable=True)

#     def callback(ch, method, properties, body):
#         data = json.loads(body)
#         print("[consumer] Received event:", data)

#         # Save event for dashboard
#         last_events.append(data)
#         if len(last_events) > 10:
#             last_events.pop(0)

#         event_type = data.get("type")
#         user_id = data.get("user_id")

#         update_fields = {}

#         if event_type == "email_updated":
#             update_fields["email"] = data.get("new_email")

#         if event_type == "address_updated":
#             update_fields["address"] = data.get("new_address")

#         if update_fields:
#             res = orders.update_many(
#                 {"user_id": user_id},
#                 {"$set": update_fields}
#             )
#             print(f"[sync] Updated {res.modified_count} orders for user {user_id}")

#         ch.basic_ack(delivery_tag=method.delivery_tag)

#     channel.basic_qos(prefetch_count=1)
#     channel.basic_consume(queue="sync_queue", on_message_callback=callback)
#     print("[consumer] Waiting for messages...")
#     channel.start_consuming()

# # ==== Start Consumer in Background Thread ====
# @app.on_event("startup")
# def start_background_consumer():
#     thread = threading.Thread(target=rabbitmq_consumer, daemon=True)
#     thread.start()

# # ==== FastAPI Endpoints ====

# @app.get("/health")
# def health():
#     return {"status": "running", "service": "event_system"}

# @app.get("/last-events")
# def get_last_events():
#     return {"events": last_events}
import pika, json, os, time, threading
from pymongo import MongoClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ==== Environment Variables ====
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
ORDER_MONGO_URI = os.environ.get("ORDER_MONGO_URI", "mongodb://mongo_order:27017/")

# ==== FastAPI App ====
app = FastAPI(
    title="Event Sync Service",
    description="Syncs user updates to order database using RabbitMQ events",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== MongoDB ====
order_client = MongoClient(ORDER_MONGO_URI)
order_db = order_client.orderdb
orders = order_db.orders

last_events = []

# ==== RabbitMQ Consumer ====
def rabbitmq_consumer():
    print("=== Starting Event Consumer ===")

    # Try to connect to RabbitMQ
    connection = None
    for attempt in range(10):
        try:
            params = pika.ConnectionParameters(host=RABBITMQ_HOST)
            connection = pika.BlockingConnection(params)
            print("Connected to RabbitMQ!")
            break
        except Exception:
            print("RabbitMQ not ready, retrying...")
            time.sleep(5)

    if not connection:
        print("Failed to connect to RabbitMQ.")
        return

    channel = connection.channel()
    channel.queue_declare(queue="sync_queue", durable=True)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        print("[consumer] Received event:", data)

        # Save last event
        last_events.append(data)
        if len(last_events) > 10:
            last_events.pop(0)

        user_id = data.get("user_id")
        update = data.get("update", {})

        update_fields = {}

        # Match User V2 event format
        if "email" in update:
            update_fields["email"] = update["email"]

        if "address" in update:
            update_fields["address"] = update["address"]

        if update_fields:
            res = orders.update_many(
                {"user_id": user_id},
                {"$set": update_fields}
            )
            print(f"[sync] Updated {res.modified_count} orders for user {user_id}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="sync_queue", on_message_callback=callback)
    channel.start_consuming()

# ==== Start Consumer Thread ====
@app.on_event("startup")
def start_consumer():
    thread = threading.Thread(target=rabbitmq_consumer, daemon=True)
    thread.start()

# ==== FastAPI Endpoints ====
@app.get("/health")
def health():
    return {"status": "ok", "service": "event_system"}

@app.get("/last-events")
def get_events():
    return {"events": last_events}
