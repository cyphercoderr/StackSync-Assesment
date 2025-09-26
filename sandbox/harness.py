# sandbox/harness.py
"""
Optional helper to build harness text from a user script. 
You can reuse this in both api and runner if desired.
"""

_RESULT_MARKER = "<<<__PY_RESULT__>>>"

def build_harness(user_script: str) -> str:
    return f"""# coding: utf-8
import json, sys
# --- user script ---
{user_script}

# --- runner ---
def __run_and_emit_result():
    try:
        result = main()
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    try:
        payload = json.dumps(result)
    except (TypeError, ValueError) as e:
        print("{_RESULT_MARKER}" + json.dumps({{"__error__": str(e)}}))
        sys.exit(2)

    print("{_RESULT_MARKER}" + payload)

if __name__ == "__main__":
    __run_and_emit_result()
"""
