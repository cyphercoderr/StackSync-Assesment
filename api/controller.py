# api/controller.py
"""
Controller / orchestrator for executing user scripts.

Responsibilities:
- call validation.validate_script(...)
- wrap the user script into a small harness that prints a single JSON RESULT marker
  so we can separate the main() return from user print() output
- execute the harness using a runner (for now a subprocess fallback)
- parse the outputs and return a normalized dict:
    {"result": <json-serializable>, "stdout": "<captured print output>", "error": "<error message or None>"}

Note: Replace the _local_runner(...) implementation with an nsjail invocation later.
"""

import tempfile
import subprocess
import sys
import os
import json
from typing import Tuple, Optional, Dict

from api.validation import validate_script

# Unique marker used to identify the JSON result (must be unlikely to collide)
_RESULT_MARKER = "<<<__PY_RESULT__>>>"

# default runtime limits
DEFAULT_TIMEOUT_SECS = 5
DEFAULT_MEMORY_MB = 128  # placeholder; not enforced by subprocess fallback


def _build_harness(script: str) -> str:
    """
    Returns Python source text that:
    - runs the user-provided script
    - calls main()
    - prints the result as a single line with a unique marker
    - leaves other print() output intact (so it shows in stdout)
    """
    # We intentionally avoid capturing/redirecting print() so that user's prints go to stdout.
    harness = f"""
import json, sys
# --- user script ---
{script}

# --- runner ---
def __run_and_emit_result():
    try:
        result = main()
    except Exception as e:
        # print error to stderr (so it's clearly an error)
        print("Exception in main():", file=sys.stderr)
        raise

    # Ensure JSON serializable; if not, we still attempt to dump and may raise
    marker = "{_RESULT_MARKER}"
    print(marker + json.dumps(result, default=lambda o: str(o)))

if __name__ == "__main__":
    __run_and_emit_result()
"""
    return harness


def _local_runner(harness_source: str, timeout: int = DEFAULT_TIMEOUT_SECS) -> Tuple[Optional[str], str, str, int]:
    """
    Simple local runner using the current Python interpreter to run the harness_source.

    Returns tuple: (result_json_text_or_None, captured_stdout, captured_stderr, return_code)

    NOTE: This is a development fallback. Replace with an nsjail runner for production.
    """
    # write harness to a temp file
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
    except subprocess.TimeoutExpired as e:
        # Kill / cleanup - subprocess.run already killed child, but ensure file removal
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None, "", f"Execution timed out after {timeout} seconds", -1

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return_code = proc.returncode

    # cleanup file
    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    # Attempt to extract the JSON result marker from stdout
    result_json_text = None
    for line in stdout.splitlines():
        if line.startswith(_RESULT_MARKER):
            result_json_text = line[len(_RESULT_MARKER):]
            # don't break: later markers override earlier ones (but unlikely)
    return result_json_text, stdout, stderr, return_code


def execute_script(script: str, timeout: int = DEFAULT_TIMEOUT_SECS, memory_mb: int = DEFAULT_MEMORY_MB) -> Dict:
    """
    High-level orchestration: validate, run in sandbox/runner, parse result.
    Returns a dict with keys:
      - result: the deserialized JSON returned by main() (or None on error)
      - stdout: captured user print() output (string)
      - error: error message string or None
    """
    ok, err = validate_script(script)
    if not ok:
        return {"result": None, "stdout": "", "error": err}

    harness = _build_harness(script)
    # TODO: swap this local runner call with a call into the nsjail runner module,
    # e.g. runner.run_in_ns_jail(harness, timeout=timeout, memory_mb=memory_mb)
    result_json_text, full_stdout, full_stderr, return_code = _local_runner(harness, timeout=timeout)

    # Separate printed stdout (excluding the result marker line(s))
    printed_lines = []
    for line in full_stdout.splitlines():
        if not line.startswith(_RESULT_MARKER):
            printed_lines.append(line)
    printed_stdout = "\n".join(printed_lines)

    if result_json_text is None:
        # No result marker found -> error
        # Use stderr + return code to form the error message
        if return_code == -1:
            error_msg = full_stderr or f"Execution timed out after {timeout} seconds."
        else:
            # If stderr is present, surface it; otherwise provide a generic message
            if full_stderr.strip():
                error_msg = full_stderr.strip()
            else:
                error_msg = f"Script did not print a result marker. Return code: {return_code}."
        return {"result": None, "stdout": printed_stdout, "error": error_msg}

    # Try to decode result_json_text
    try:
        result_obj = json.loads(result_json_text)
    except Exception as e:
        return {"result": None, "stdout": printed_stdout, "error": f"Returned value is not valid JSON: {e}"}

    # Successful run
    return {"result": result_obj, "stdout": printed_stdout, "error": None}
