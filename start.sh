#!/bin/bash

# Quick start script for School Risk Detection MVP
# This script helps you get the system up and running

set -e

echo "================================================"
echo "School Risk Detection MVP - Quick Start"
echo "================================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not installed."
    echo "Please install Docker Compose plugin: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if NVIDIA Docker runtime is available
if ! docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "WARNING: NVIDIA Docker runtime not detected or not working."
    echo "The DeepStream analytics service requires NVIDIA GPU."
    echo "Please install nvidia-container-toolkit if you have an NVIDIA GPU."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✓ Docker is installed"
echo "✓ Docker Compose is installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "NOTE: Please review and update .env file with your settings,"
    echo "especially the SECRET_KEY for production use."
    echo ""
fi

# Create cameras config if it doesn't exist
if [ ! -f configs/cameras.yaml ]; then
    echo "Creating cameras configuration from template..."
    cp configs/cameras.example.yaml configs/cameras.yaml
    echo "✓ Created configs/cameras.yaml"
    echo ""
    echo "NOTE: Please update configs/cameras.yaml with your camera RTSP URLs."
    echo ""
fi

# Build and start services
echo "Building Docker images..."
docker compose build

echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "Checking service status..."
docker compose ps

echo ""
echo "================================================"
echo "✓ School Risk Detection MVP is starting!"
echo "================================================"
echo ""
echo "Services:"
echo "  - Web UI: http://localhost:3000"
echo "  - Risk Engine API: http://localhost:8001"
echo "  - Clip Service API: http://localhost:8002"
echo ""
echo "Default login credentials:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "IMPORTANT: Change the default password after first login!"
echo ""
echo "To view logs:"
echo "  docker compose logs -f"
echo ""
echo "To stop:"
echo "  docker compose down"
echo ""
echo "For more information, see README.md"
echo "================================================"
