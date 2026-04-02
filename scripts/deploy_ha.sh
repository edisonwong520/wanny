#!/bin/bash
# Description: Script to deploy Home Assistant with Midea component via Docker Compose
# References: Based on user command history and configuration requirements

set -e

# Get project root (parent directory of scripts/)
PRJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source of configuration files
DOCKER_SRC_DIR="$PRJ_ROOT/docker/homeassistant"
# Target deployment directory
DEPLOY_DIR="$PRJ_ROOT/deploy/homeassistant"

echo "🚀 Preparing Home Assistant deployment..."
echo "📂 Source: $DOCKER_SRC_DIR"
echo "📂 Target: $DEPLOY_DIR"

# 1. Create deployment directory structure
mkdir -p "$DEPLOY_DIR/config/custom_components"

# 2. Copy docker-compose.yaml from source to deployment directory
if [ -f "$DOCKER_SRC_DIR/docker-compose.yaml" ]; then
    echo "📋 Copying docker-compose.yaml to deployment directory..."
    cp "$DOCKER_SRC_DIR/docker-compose.yaml" "$DEPLOY_DIR/docker-compose.yaml"
else
    echo "❌ Error: $DOCKER_SRC_DIR/docker-compose.yaml not found!"
    exit 1
fi

# 3. Enter deployment directory
cd "$DEPLOY_DIR"

# 4. Start Docker container
echo "📦 Starting Home Assistant container..."
docker compose up -d

# 5. Clone and install midea_auto_cloud component
echo "📎 Installing midea_auto_cloud component..."
TEMP_CLONE_DIR="/tmp/midea_auto_cloud_$(date +%s)"
git clone git@github.com:sususweet/midea_auto_cloud.git "$TEMP_CLONE_DIR"

# Copy component to config directory
cp -R "$TEMP_CLONE_DIR/custom_components/midea_auto_cloud" "$DEPLOY_DIR/config/custom_components/"

# Clean up temp clone
rm -rf "$TEMP_CLONE_DIR"

# 6. Restart to apply changes
echo "🔄 Restarting Home Assistant to load components..."
docker compose restart

echo "✅ Home Assistant deployment finished."
echo "🔗 Access your Home Assistant at: http://localhost:8123"
