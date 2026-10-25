# ── Stage 1: Build the React Frontend ─────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python Backend & Production Runtime ─────────────
FROM python:3.11-slim

# Prevent python from writing pyc files & enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV HOME=/home/user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first (compact wheel)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir ezkl

# Copy project files
COPY backend ./backend
COPY contracts ./contracts
COPY models ./models
COPY scripts ./scripts
COPY data ./data

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Setup Hugging Face compatible non-root user (UID 1000)
RUN useradd -m -u 1000 user && \
    mkdir -p /app/data /app/models/ezkl_artifacts_trustmark /home/user/.cache && \
    chown -R user:user /app /home/user

USER user

# Pre-compile / generate circuit artifacts on build if missing
RUN python scripts/setup_trustmark_zkp.py || true

EXPOSE 7860

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
