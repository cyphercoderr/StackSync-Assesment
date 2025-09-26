"""
Controller / orchestrator for executing user scripts.

Tries to use a remote runner service (RUNNER_URL) and falls back to local execution
if the runner is unreachable. Keeps the same harness semantics and markers.
"""

import tempfile
import subprocess
import sys
import os
import json
from typing import Tuple, Optional, Dict

import requests

from api.validation import validate_script

# Unique marker used to identify the JSON result (must be unlikely to collide)
_RESULT_MARKER = "<<<__PY_RESULT__>>>"

# default runtime limits
DEFAULT_TIMEOUT_SECS = 5
DEFAULT_MEMORY_MB = 128  # placeholder; not enforced by subprocess fallback

# Runner URL (container DNS / service name). When using docker-compose this resolves to the runner service.
RUNNER_URL = os.environ.get("RUNNER_URL", "http://sandbox-runner:5000/run")
REQUEST_TIMEOUT = int(os.environ.get("RUNNER_REQUEST_TIMEOUT", "10"))


def _build_harness(script: str) -> str:
    """
    Build the harness (same semantics as before).
    """
    harness = f"""# coding: utf-8
import json, sys
# --- user script ---
{script}

# --- runner ---
def __run_and_emit_result():
    try:
        result = main()
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    # Ensure result is JSON-serializable; fail loudly otherwise
    try:
        payload = json.dumps(result)
    except (TypeError, ValueError) as e:
        err = {{ "error": "result_not_json_serializable", "detail": str(e) }}
        # emit a recognizable error marker on stderr (runner may forward this)
        print("{_RESULT_MARKER}" + json.dumps({{"__error__": str(e)}}))
        sys.exit(2)

    print("{_RESULT_MARKER}" + payload)

if __name__ == "__main__":
    __run_and_emit_result()
"""
    return harness


def _local_runner(harness_source: str, timeout: int = DEFAULT_TIMEOUT_SECS) -> Tuple[Optional[str], str, str, int]:
    """
    Local fallback runner using current python interpreter (unchanged behavior).
    """
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    try:
        tmp.write(harness_source)
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
    except subprocess.TimeoutExpired:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None, "", f"Execution timed out after {timeout} seconds", -1

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return_code = proc.returncode

    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    result_json_text = None
    for line in stdout.splitlines():
        if line.startswith(_RESULT_MARKER):
            result_json_text = line[len(_RESULT_MARKER):]
    return result_json_text, stdout, stderr, return_code


def _remote_runner(harness_source: str, timeout: int = DEFAULT_TIMEOUT_SECS) -> Tuple[Optional[str], str, str, int]:
    """
    Send the harness to the remote runner service and return (result_json_text, stdout, stderr, return_code).
    Expects the runner to return JSON with keys: stdout, stderr, return_code.
    """
    payload = {"harness": harness_source, "timeout": timeout}
    resp = requests.post(RUNNER_URL, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    stdout = body.get("stdout", "")
    stderr = body.get("stderr", "")
    return_code = int(body.get("return_code", 1))
    result_json_text = None
    for line in stdout.splitlines():
        if line.startswith(_RESULT_MARKER):
            result_json_text = line[len(_RESULT_MARKER):]
    return result_json_text, stdout, stderr, return_code


def execute_script(script: str, timeout: int = DEFAULT_TIMEOUT_SECS, memory_mb: int = DEFAULT_MEMORY_MB) -> Dict:
    """
    Validate script, attempt remote runner, fallback to local runner, parse, and return structure.
    """
    ok, err = validate_script(script)
    if not ok:
        return {"result": None, "stdout": "", "error": err}

    harness = _build_harness(script)

    # Try remote runner first (if reachable). If RUNNER_URL points to nowhere requests will raise.
    try:
        result_json_text, full_stdout, full_stderr, return_code = _remote_runner(harness, timeout=timeout)
    except Exception as e:
        # Remote runner unavailable: log the exception as part of stderr fallback note and run locally.
        fallback_note = f"[runner-unavailable] {e}"
        result_json_text, full_stdout, full_stderr, return_code = _local_runner(harness, timeout=timeout)
        # Prepend fallback note to stderr so caller sees remote failure reason (keeps behavior observable)
        if full_stderr:
            full_stderr = fallback_note + "\n" + full_stderr
        else:
            full_stderr = fallback_note

    # Collect printed stdout excluding _RESULT_MARKER lines
    printed_lines = []
    for line in full_stdout.splitlines():
        if not line.startswith(_RESULT_MARKER):
            printed_lines.append(line)
    printed_stdout = "\n".join(printed_lines)

    if result_json_text is None:
        # No JSON result; report helpful error using stderr or return code
        if full_stderr and full_stderr.strip():
            return {"result": None, "stdout": printed_stdout, "error": full_stderr.strip()}
        if return_code == -1:
            return {"result": None, "stdout": printed_stdout, "error": f"Execution timed out after {timeout} seconds."}
        return {"result": None, "stdout": printed_stdout, "error": f"Script did not produce a JSON result (return code {return_code})."}

    # Parse JSON result
    try:
        result_obj = json.loads(result_json_text)
    except Exception as e:
        return {"result": None, "stdout": printed_stdout, "error": f"Returned value is not valid JSON: {e}"}

    return {"result": result_obj, "stdout": printed_stdout, "error": None}
