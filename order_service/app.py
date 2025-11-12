from flask import Flask, request, jsonify
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("ORDER_MONGO_URI", "mongodb://mongo_order:27017/")

app = Flask(__name__)
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.orderdb
orders = db.orders

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "component": "order_service"}), 200

@app.route("/order", methods=["POST"])
def create_order():
    data = request.get_json(force=True)
    required = {"order_id","user_id","items","status","email","address"}
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": "missing fields", "fields": missing}), 400
    orders.update_one({"order_id": data["order_id"]}, {"$set": data}, upsert=True)
    return jsonify({"message": "Order created/updated", "order": data}), 201

@app.route("/orders/<status>", methods=["GET"])
def get_orders(status):
    result = list(orders.find({"status": status}, {"_id": 0}))
    return jsonify(result), 200

@app.route("/order/<order_id>", methods=["PUT"])
def update_order(order_id):
    data = request.get_json(force=True)
    orders.update_one({"order_id": order_id}, {"$set": data}, upsert=True)
    return jsonify({"message": "Order updated"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
