import pika, json, os, time, threading
from pymongo import MongoClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
ORDER_MONGO_URI = os.environ.get("ORDER_MONGO_URI", "mongodb://mongo_order:27017/")

order_client = MongoClient(ORDER_MONGO_URI)
order_db = order_client.orderdb
orders = order_db.orders

last_events = []

def rabbitmq_consumer():
    print("=== Event Consumer Starting ===")
    connection = None

    for attempt in range(10):
        try:
            params = pika.ConnectionParameters(host=RABBITMQ_HOST)
            connection = pika.BlockingConnection(params)
            print("Connected to RabbitMQ")
            break
        except Exception:
            print("RabbitMQ not ready, retrying...")
            time.sleep(5)

    if not connection:
        print("Connection failed")
        return

    channel = connection.channel()
    channel.queue_declare(queue="sync_queue", durable=True)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        print("Event received:", data)

        last_events.append(data)
        if len(last_events) > 10:
            last_events.pop(0)

        update_fields = data.get("update", {})
        user_id = data.get("user_id")

        if update_fields:
            orders.update_many({"user_id": user_id}, {"$set": update_fields})

        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="sync_queue", on_message_callback=callback)
    channel.start_consuming()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 FastAPI starting, launching consumer thread...")
    thread = threading.Thread(target=rabbitmq_consumer, daemon=True)
    thread.start()

    yield

    print("FastAPI shutdown")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "event_system"}

@app.get("/last-events")
def last():
    return {"events": last_events}
