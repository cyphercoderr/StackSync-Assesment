# sandbox.Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash runneruser
WORKDIR /home/runneruser/runner

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ./sandbox ./sandbox

ENV PYTHONUNBUFFERED=1
EXPOSE 5000

USER runneruser
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "sandbox.runner:app"]
