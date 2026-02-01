# syntax=docker/dockerfile:1
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

WORKDIR /app

# Install system dependencies with cache mount
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config

# Copy only requirements first for better layer caching
COPY requirements.txt .

# Install dependencies with pip cache (skip torch since it's in base image)
RUN --mount=type=cache,target=/root/.cache/pip \
    grep -v "^torch==" requirements.txt | grep -v "^#" | grep -v "^$" > /tmp/requirements_filtered.txt && \
    pip install -r /tmp/requirements_filtered.txt && \
    rm /tmp/requirements_filtered.txt

# Create directories
RUN mkdir -p /app/data/json /app/logs

# Copy application code last (changes most frequently)
COPY app/ .

CMD ["python", "main.py"]
