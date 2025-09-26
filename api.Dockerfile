# api.Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /home/appuser/app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy API package
COPY ./api ./api

ENV PYTHONPATH=/home/appuser/app
ENV FLASK_ENV=production
ENV PORT=8081
EXPOSE 8081

USER appuser
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8081", "api.main:app"]
