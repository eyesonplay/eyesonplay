# Build context: repository root (the worker depends on ../event-engine).
#   cpu      - mock mode; no torch (default, used by docker-compose.yml)
#   real-cpu - real computer vision on CPU (ultralytics + CPU torch), e.g. on a Mac
#   gpu      - real computer vision on NVIDIA GPUs (CUDA torch, NVML metrics)

FROM python:3.12-slim AS cpu
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY event-engine /src/event-engine
RUN pip install /src/event-engine
COPY inference-worker/pyproject.toml ./
COPY inference-worker/worker ./worker
RUN pip install .
RUN useradd --create-home --uid 10001 worker && mkdir -p /data/media /data/models && chown -R worker /data
USER worker
# Ultralytics downloads stock weights into the working directory (a volume).
WORKDIR /data/models
CMD ["python", "-m", "worker.main"]

FROM cpu AS real-cpu
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install "/app[real]"
USER worker

# CUDA 12 matches the PyTorch cu124 wheels below and runs on NVIDIA drivers >= 525;
# a CUDA 13 base image refuses to start on hosts with older drivers.
FROM nvidia/cuda:12.9.2-cudnn-runtime-ubuntu24.04 AS gpu
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
WORKDIR /app
COPY event-engine /src/event-engine
RUN pip install /src/event-engine
COPY inference-worker/pyproject.toml ./
COPY inference-worker/worker ./worker
RUN pip install ".[real]"
RUN useradd --create-home --uid 10001 worker && mkdir -p /data/media /data/models && chown -R worker /data
USER worker
WORKDIR /data/models
CMD ["python", "-m", "worker.main"]
