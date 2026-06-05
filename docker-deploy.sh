#!/bin/bash
set -e

echo "=== LogSage AI — Docker Deployment ==="

# Build and start all services
docker compose down --remove-orphans
docker compose build --no-cache
docker compose up -d

echo "Waiting for services to be healthy..."
sleep 10

# Check health
docker compose ps

echo ""
echo "=== Deployment Complete ==="
echo "LogSage AI: http://localhost:8501"
echo "Ollama API: http://localhost:11434"
echo ""
echo "To view logs: docker compose logs -f logsage"
echo "To stop:      docker compose down"
