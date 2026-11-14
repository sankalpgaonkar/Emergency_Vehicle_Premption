FROM python:3.11-slim

# Prevent Python from writing .pyc and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5050

# Install minimal OS dependencies for OpenCV and video transcoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install CPU-only PyTorch first (saves ~2 GB download)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install application dependencies
COPY demo_app/requirements.txt demo_app/requirements.txt
RUN pip install --no-cache-dir -r demo_app/requirements.txt

# Copy application files and model weights
COPY demo_app/ demo_app/
COPY project/models/ project/models/

EXPOSE 5050

# Launch server binding to 0.0.0.0 and PORT assigned by Render
CMD ["sh", "-c", "python demo_app/app.py --host 0.0.0.0 --port ${PORT:-5050}"]

