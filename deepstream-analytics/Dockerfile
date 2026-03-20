FROM python:3.11-slim

# Install system dependencies for OpenCV and video processing
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    python3-opencv \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgstreamer1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-libav \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p /app/config /app/models /app/cache /app/logs

# Download YOLOv8 model (lightweight for people detection)
RUN pip3 install ultralytics && \
    python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

ENV PYTHONUNBUFFERED=1

CMD ["python3", "analytics_service.py"]
