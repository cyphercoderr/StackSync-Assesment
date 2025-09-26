# Python Script Execution Service

## 📌 Overview

This project provides a **secure API service** that allows clients to submit arbitrary Python scripts and receive the result of the `main()` function execution.  
It is designed to meet the following business requirements:

- Expose a simple **Flask API** (`/execute`) for submitting scripts.
- Ensure **input validation** (only valid scripts with a `main()` function are accepted).
- **Isolate execution** using [`nsjail`](https://nsjail.dev/) to protect against malicious code.
- Support commonly needed libraries (`os`, `numpy`, `pandas`).
- Provide **modular, production-ready code**, easily deployable on **Google Cloud Run**.
- Return results in a structured JSON response:
  ```json
  {
    "result": {...},   # JSON returned by main()
    "stdout": "...",   # Print output from script execution
    "error": null      # Or error details if failed
  }

## Architecture
```bash
                +--------------------+
                |    Client (User)   |
                +--------------------+
                         |
                         v
              POST /execute { "script": "..." }
                         |
         +---------------+---------------+
         |                               |
         v                               v
+-------------------+          +--------------------+
|   Flask API (8080)|  ----->  |  Sandbox Runner    |
|   - Validation    |          |  (nsjail + Python) |
|   - Controller    |          |  - Executes script |
|                   |          |  - Captures stdout |
+-------------------+          +--------------------+
```
**API Service (Flask)**

* Handles /health and /execute endpoints.
* Validates scripts (syntax, presence of main(), disallowed imports).
* Delegates execution to the sandbox.

## Sandbox Runner (nsjail)

* Executes script safely in an isolated environment.
* Restricts CPU, memory, and networking.
* Ensures malicious scripts cannot escape.

## Running Locally

1. Install Requirements (API or Sandbox)
```bash
pip install -r requirements.txt
```
2. Run API Service Locally
```bash
python -m api.main
```

API will be available at: http://localhost:8080

## Running with Docker
**Build & Start Services**
```bash
docker-compose up --build
```

API service → http://localhost:8080

Sandbox runner → http://sandbox:8081


## Example Usage
**Health Check**
```bash
curl -X GET http://localhost:8080/health

Execute Script
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def main():\n    print(\"hello from sandbox\")\n    return {\"message\": \"success\"}"
  }'
```

## Expected Response:
```bash
{
  "result": { "message": "success" },
  "stdout": "hello from sandbox",
  "error": null
}
```

## Testing
* Unit Tests
* Tests are placed under tests/ and include:
* Validation tests
* Missing main() function → should return error
* Use of eval/exec → should be rejected
* Oversized scripts (>200KB) → should be rejected
* Execution tests
* main() returns JSON → valid result
* main() raises exception → returns error
* Script prints to stdout → output captured

## Run Tests
```bash
pytest -v
```
## Edge Cases Considered

* No main() function
* def foo(): return {"x": 1}
→ Error: script must define main().
* Invalid JSON return
* def main(): return set([1, 2])
→ Error: "Returned value is not valid JSON".
* Malicious code attempt
```bash
import os
def main(): os.system("rm -rf /")
```
→ Blocked by validation & nsjail.
* Infinite loop
def main():
    while True: pass

→ Terminated by nsjail timeout.

Large script size (>200KB)
→ Rejected at validation step.

## Development Notes

* Modular code: API logic, validation, and sandbox execution are decoupled.
* Sandbox isolation: nsjail ensures execution is safe even if validation is bypassed.
* Production-ready: Small Docker images, simple docker run startup, and Cloud Run compatible.