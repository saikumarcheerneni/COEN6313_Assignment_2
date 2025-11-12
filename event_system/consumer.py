import pika, json, os, time
from pymongo import MongoClient

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
ORDER_MONGO_URI = os.environ.get("ORDER_MONGO_URI", "mongodb://mongo_order:27017/")

def main():
    print("=== [consumer] Starting Event Consumer ===")
    print(f"[consumer] RabbitMQ host: {RABBITMQ_HOST}")
    print(f"[consumer] Mongo URI: {ORDER_MONGO_URI}")

    # Connect to MongoDB
    order_client = MongoClient(ORDER_MONGO_URI)
    order_db = order_client.orderdb
    orders = order_db.orders

    # Connect to RabbitMQ with retry logic
    params = pika.ConnectionParameters(host=RABBITMQ_HOST)
    connection = None
    for attempt in range(10):
        try:
            print(f"[consumer] Attempting RabbitMQ connection ({attempt+1}/10)...")
            connection = pika.BlockingConnection(params)
            print("[consumer] Connected to RabbitMQ!")
            break
        except pika.exceptions.AMQPConnectionError:
            print("[consumer] RabbitMQ not ready, retrying in 5 seconds...")
            time.sleep(5)

    if not connection:
        print("[consumer] Failed to connect to RabbitMQ after multiple attempts.")
        return

    channel = connection.channel()
    channel.queue_declare(queue='sync_queue', durable=True)

    # Define callback for handling messages
    def callback(ch, method, properties, body):
        try:
            data = json.loads(body)
            user_id = data.get('user_id')
            update = data.get('update', {})

            if not user_id or not update:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            allowed = {k: v for k, v in update.items() if k in {"email", "address"}}
            if allowed:
                res = orders.update_many({"user_id": user_id}, {"$set": allowed})
                print(f"[sync] Updated {res.modified_count} orders for user {user_id}")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            print("Error processing message:", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='sync_queue', on_message_callback=callback)
    print("[consumer] Waiting for messages on 'sync_queue'...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
