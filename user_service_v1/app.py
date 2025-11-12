from flask import Flask, request, jsonify
from pymongo import MongoClient
import pika, json, os

MONGO_URI = os.environ.get("USER_MONGO_URI", "mongodb://mongo_user:27017/")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")

app = Flask(__name__)
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.userdb
users = db.users

def get_rabbit_channel():
    params = pika.ConnectionParameters(host=RABBITMQ_HOST)
    connection = pika.BlockingConnection(params)
    ch = connection.channel()
    ch.queue_declare(queue='sync_queue', durable=True)
    return connection, ch

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "component": "user_v1"}), 200

@app.route("/user", methods=["POST"])
def create_user():
    data = request.get_json(force=True)
    if not data or "user_id" not in data:
        return jsonify({"error": "user_id required"}), 400
    users.update_one({"user_id": data["user_id"]}, {"$set": data}, upsert=True)
    return jsonify({"message": "User created/updated", "user": data}), 201

@app.route("/user/<user_id>", methods=["PUT"])
def update_user(user_id):
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "no update payload"}), 400
    users.update_one({"user_id": user_id}, {"$set": data}, upsert=True)

    payload = {"user_id": user_id, "update": {}}
    for k in ["email", "address"]:
        if k in data:
            payload["update"][k] = data[k]

    if payload["update"]:
        try:
            conn, ch = get_rabbit_channel()
            ch.basic_publish(
                exchange="",
                routing_key="sync_queue",
                body=json.dumps(payload).encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            conn.close()
        except Exception as e:
            return jsonify({"message": "User updated but event publish failed", "error": str(e)}), 202

    return jsonify({"message": "User updated", "event_published": bool(payload["update"])}), 200
@app.route("/user/<user_id>", methods=["GET"])
def get_user(user_id):
    user = users.find_one({"user_id": user_id}, {"_id": 0})
    if user:
        return jsonify(user), 200
    else:
        return jsonify({"error": "User not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
