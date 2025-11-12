from flask import Flask, request, jsonify, Response
import requests, json, random, os

app = Flask(__name__)

CONFIG_PATH = os.environ.get("GATEWAY_CONFIG", "config.json")

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"P": 0.5}  # default 50/50

def choose_user_service():
    cfg = load_config()
    P = float(cfg.get("P", 0.5))
    return "http://user_v1:5001" if random.random() < P else "http://user_v2:5003"

ORDER_BASE = "http://order_service:5002"

def _forward(base):
    url = f"{base}{request.path}"
    try:
        r = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            json=(request.get_json(silent=True) if request.method in ["POST","PUT","PATCH"] else None),
            timeout=10
        )
        headers = {"Content-Type": r.headers.get("Content-Type","application/json")}
        return Response(r.content, status=r.status_code, headers=headers)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "service_unreachable", "detail": str(e)}), 502

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "component": "api_gateway"}), 200

@app.route("/user", methods=["POST"])
def gw_user_create():
    return _forward(choose_user_service())

@app.route("/user/<path:subpath>", methods=["PUT","GET"])
def gw_user_update(subpath):
    return _forward(choose_user_service())

@app.route("/order", methods=["POST","PUT","GET"])
@app.route("/order/<path:subpath>", methods=["POST","PUT","GET"])
@app.route("/orders", methods=["GET"])
@app.route("/orders/<path:subpath>", methods=["GET"])
def gw_order_proxy(subpath=None):
    return _forward(ORDER_BASE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
