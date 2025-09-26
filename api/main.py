# api/main.py
"""
Flask entrypoint for the sandbox execution API.
"""

from flask import Flask, request, jsonify
import logging
from api.controller import execute_script

app = Flask(__name__)

# Basic logging config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


@app.route("/execute", methods=["POST"])
def execute():
    # Ensure valid JSON payload
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON payload."}), 400

    if not data or "script" not in data:
        return jsonify({"error": "Missing required field 'script' in JSON body."}), 400

    script = data.get("script")
    # Call controller
    res = execute_script(script, timeout=5, memory_mb=128)

    if res.get("error"):
        # Log error for auditing
        logger.warning("Script execution error: %s", res["error"])
        return jsonify({"error": res["error"], "stdout": res.get("stdout", "")}), 400

    return jsonify({"result": res["result"], "stdout": res.get("stdout", "")}), 200


if __name__ == "__main__":
    # For local development:
    # Run with: python -m api.main  (run from project/ parent directory)
    app.run(host="0.0.0.0", port=8081)
