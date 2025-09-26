###############################################################################
# Builder stage - builds nsjail
###############################################################################
FROM debian:bookworm-slim AS builder

# Install build deps for nsjail (kept in builder only)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    pkg-config \
    protobuf-compiler \
    libprotobuf-dev \
    libnl-route-3-dev \
    libcap-dev \
    libseccomp-dev \
    flex \
    bison \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
# Clone and build nsjail
RUN git clone https://github.com/google/nsjail.git /tmp/nsjail \
    && make -C /tmp/nsjail \
    && strip /tmp/nsjail/nsjail

###############################################################################
# Final runtime image (small)
###############################################################################
FROM python:3.11-slim

# Runtime deps required by nsjail binary (small set). Add only what is necessary.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcap2 \
    libseccomp2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy nsjail binary from builder
COPY --from=builder /tmp/nsjail/nsjail /usr/local/bin/nsjail
RUN chmod +x /usr/local/bin/nsjail

# Create non-root user (keep behaviour compatible with your current file)
RUN useradd --create-home --shell /bin/bash runneruser
WORKDIR /home/runneruser/runner

# Copy python deps & install (your existing requirements.txt)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy your sandbox service dir (no functional change)
COPY ./sandbox ./sandbox

# Copy the example nsjail config into the image (you can customize later)
COPY ./sandbox/nsjail.cfg /etc/nsjail.cfg

ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# Keep the same non-root user and CMD that your repo already uses
USER runneruser
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "sandbox.runner:app"]
