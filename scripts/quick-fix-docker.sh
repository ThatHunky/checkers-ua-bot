#!/bin/bash
# Quick fix: Just start the Docker daemon

echo "Attempting to start Docker daemon..."

# Try systemd first
if systemctl is-active --quiet docker 2>/dev/null; then
    echo "✓ Docker is already running"
else
    sudo systemctl start docker
    sudo systemctl enable docker
    echo "✓ Docker daemon started and enabled"
fi

# Verify
if docker ps > /dev/null 2>&1; then
    echo "✓ Docker is working!"
    docker --version
else
    echo "✗ Docker still not working. You may need to reinstall."
    echo "  Run: ./scripts/reinstall-docker.sh"
fi
