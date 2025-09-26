# sandbox/runner.py
"""
Runner service that executes given harness Python source.

This is the container that will run untrusted code in production (replace the subprocess.run
call with nsjail invocation when ready). For now it executes harness with subprocess
and returns stdout/stderr/return_code to the API.
"""

from flask import Flask, request, jsonify
import tempfile
import subprocess
import sys
import os
import traceback

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


@app.route("/run", methods=["POST"])
def run_harness():
    """
    Request JSON format:
      { "harness": "<python source>", "timeout": <int seconds> }

    Response JSON format:
      { "stdout": "<stdout string>", "stderr": "<stderr string>", "return_code": <int> }
    """
    data = request.get_json(force=True)
    harness = data.get("harness")
    timeout = int(data.get("timeout", 5))

    if not harness or not isinstance(harness, str):
        return jsonify({"error": "Missing or invalid 'harness'"}), 400

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    try:
        tmp.write(harness)
        tmp.flush()
        tmp_path = tmp.name
    finally:
        tmp.close()

    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        return_code = proc.returncode
    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = f"Execution timed out after {timeout} seconds"
        return_code = -1
    except Exception:
        stdout = ""
        stderr = f"Runner internal error:\\n{traceback.format_exc()}"
        return_code = -2
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return jsonify({"stdout": stdout, "stderr": stderr, "return_code": return_code})


if __name__ == "__main__":
    # for local debug
    app.run(host="0.0.0.0", port=5000)
