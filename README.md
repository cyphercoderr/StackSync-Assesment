# 🐍 Python Script Execution Service

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
    "result": {...},   // JSON returned by main()
    "stdout": "...",   // Print output from script execution
    "error": null      // Or error details if failed
  }
````

---

##  Architecture

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

### **API Service (Flask)**

* Handles `/health` and `/execute` endpoints.
* Validates scripts (syntax, presence of `main()`, disallowed imports).
* Delegates execution to the sandbox.

### **Sandbox Runner (nsjail)**

* Executes script safely in an isolated environment.
* Restricts CPU, memory, and networking.
* Ensures malicious scripts cannot escape.

---

## ⚙️ Running Locally

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the API:

   ```bash
   export FLASK_APP=sandbox.runner:app
   flask run --host=0.0.0.0 --port=8080
   ```

API will be available at: [http://localhost:8080](http://localhost:8080)

---

## 🐳 Running with Docker

**Build & Start Service**

```bash
docker build -t sandbox-runner .
docker run -p 8080:8080 sandbox-runner
```

API service → [http://localhost:8080](http://localhost:8080)

---

##  Deploying to Google Cloud Run

```bash
gcloud run deploy sandbox-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

Example request after deployment:

```bash
curl -X POST https://<YOUR-CLOUD-RUN-URL>/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "def main():\n    return {\"msg\": \"Hello from Cloud Run\"}"}'
```

---

## Example Usage

### Health Check

```bash
curl -X GET http://localhost:8080/health
```

### Execute Script

```bash
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{
    "script": "def main():\n    print(\"hello from sandbox\")\n    return {\"message\": \"success\"}"
  }'
```

### Expected Response

```json
{
  "result": { "message": "success" },
  "stdout": "hello from sandbox",
  "error": null
}
```

---

##  Testing

Unit tests are included under `tests/` and cover:

* **Validation tests**

  * Missing `main()` function → should return error.
  * Use of `eval`/`exec` → should be rejected.
  * Oversized scripts (>200KB) → should be rejected.

* **Execution tests**

  * `main()` returns JSON → valid result.
  * `main()` raises exception → error returned.
  * Script prints to stdout → output captured.

Run tests with:

```bash
pytest -v
```

---

## ⚡ Edge Cases Considered

* **No `main()` function**

  ```python
  def foo(): return {"x": 1}
  ```

  → Error: `script must define main()`

* **Invalid JSON return**

  ```python
  def main(): return set([1, 2])
  ```

  → Error: `"Returned value is not valid JSON"`

* **Malicious code attempt**

  ```python
  import os
  def main(): os.system("rm -rf /")
  ```

  → Blocked by validation & nsjail

* **Infinite loop**

  ```python
  def main():
      while True: pass
  ```

  → Terminated by nsjail timeout

* **Large script size (>200KB)**
  → Rejected at validation step

---

## Development Notes

* **Modular code** → API logic, validation, and sandbox execution are decoupled.
* **Sandbox isolation** → nsjail ensures execution is safe even if validation is bypassed.
* **Production-ready** → Small Docker image, `docker run` startup, and Cloud Run compatible.
* **Benchmark time** → Approx. 5–6 hours including design, coding, testing, and documentation.

---
