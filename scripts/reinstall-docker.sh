#!/bin/bash
# Complete Docker removal and reinstallation script for Debian.
#
# THIS IS NOT PROJECT TOOLING. It is host repair: it purges the Docker packages and
# the Docker APT repository, which stops EVERY container on the machine, not just
# this bot's. Read it before running it.

set -euo pipefail

echo "=== Docker Complete Reinstallation Script ==="
echo ""
echo "This will REMOVE Docker from this machine and reinstall it."
echo "Every running container will stop, including ones unrelated to this project."
echo ""
if command -v docker >/dev/null 2>&1; then
    echo "Containers currently running on this host:"
    docker ps --format '  - {{.Names}} ({{.Image}})' 2>/dev/null || echo "  (could not list)"
    echo ""
fi
read -r -p "Continue? Type 'yes' to proceed: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted. Nothing was changed."
    exit 1
fi
echo ""

# Step 1: Stop Docker service
echo "[1/7] Stopping Docker service..."
sudo systemctl stop docker 2>/dev/null || true
sudo systemctl stop docker.socket 2>/dev/null || true
sudo service docker stop 2>/dev/null || true

# Step 2: Remove all Docker packages
echo "[2/7] Removing Docker packages..."
sudo apt-get remove -y docker docker-engine docker.io containerd runc \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
    docker-compose-plugin docker-ce-rootless-extras docker-cli \
    docker-model-plugin 2>/dev/null || true

# Step 3: Remove Docker repositories
echo "[3/7] Removing Docker repositories..."
sudo rm -f /etc/apt/sources.list.d/docker.list \
           /etc/apt/keyrings/docker.gpg \
           /etc/apt/sources.list.d/docker-ce.list 2>/dev/null || true

# Step 4: Clean up Docker data (optional - uncomment if you want to remove all data)
echo "[4/7] Removing Docker data and configuration..."
read -r -p "Remove all Docker data (containers, images, volumes)? [y/N] " -n 1 REPLY
echo
if [[ "${REPLY:-}" =~ ^[Yy]$ ]]; then
    sudo rm -rf /var/lib/docker /var/lib/containerd /etc/docker
    rm -rf "$HOME/.docker"
    echo "  ✓ Docker data removed"
else
    echo "  ⊘ Keeping Docker data (will be reused after reinstall)"
fi

# Step 5: Update package index
echo "[5/7] Updating package index..."
sudo apt-get update

# Step 6: Install Docker prerequisites
echo "[6/7] Installing prerequisites..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Step 7: Add Docker's official GPG key and repository
echo "[7/7] Installing Docker..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine, CLI, and Compose
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Step 8: Start and enable Docker
echo "Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

# Step 9: Add current user to docker group (optional)
echo ""
read -r -p "Add current user (${USER:-$(id -un)}) to docker group? [y/N] " -n 1 REPLY
echo
if [[ "${REPLY:-}" =~ ^[Yy]$ ]]; then
    sudo usermod -aG docker "${USER:-$(id -un)}"
    echo "  ✓ User added to docker group"
    echo "  ! You may need to log out and back in for this to take effect"
fi

# Step 10: Verify installation
echo ""
echo "=== Verification ==="
docker --version
docker compose version
sudo systemctl status docker --no-pager | head -5

echo ""
echo "✓ Docker reinstallation complete!"
echo ""
echo "If you added yourself to the docker group, you may need to:"
echo "  - Log out and log back in, OR"
echo "  - Run: newgrp docker"
