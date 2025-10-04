#!/bin/bash

# Local development setup script

set -e

echo "🔧 Setting up local development environment..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and configure your tokens and settings!"
fi

# Create logs directory
mkdir -p logs

# Build and start containers
echo "🐳 Starting Docker containers..."
docker-compose down 2>/dev/null || true
docker-compose build
docker-compose up -d

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 5

# Check container status
echo "📊 Container status:"
docker-compose ps

echo "✅ Local setup completed!"
echo "🔍 To view logs: docker-compose logs -f"
echo "🛑 To stop: docker-compose down"