#!/bin/bash
# Teardown script for Narrator Docker development environment

set -e  # Exit on error

echo "🧹 Tearing down Narrator Docker environment..."

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    exit 1
fi

# Stop and remove containers
echo "🛑 Stopping containers..."
if docker compose version &> /dev/null 2>&1; then
    docker compose down
else
    docker-compose down
fi

# Ask about removing volumes
read -p "❓ Do you want to remove the database volume (all data will be lost)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing volumes..."
    if docker compose version &> /dev/null 2>&1; then
        docker compose down -v
    else
        docker-compose down -v
    fi
    echo "✅ All containers and volumes removed!"
else
    echo "✅ Containers stopped (data preserved in volume)"
fi

echo ""
echo "🎉 Teardown complete!"
