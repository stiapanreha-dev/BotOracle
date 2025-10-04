#!/bin/bash

# Deployment script for Pi4-2
# Usage: ./scripts/deploy.sh

set -e

# Configuration
REMOTE_HOST="Pi4-2"
REMOTE_USER="lexun"
REMOTE_PATH="/home/lexun/ai-consultant"
REPO_URL="git@NTMY:stepun/ai-consultant.git"

echo "🚀 Starting deployment to Pi4-2..."

# Build and push to git
echo "📦 Building and pushing to git..."
git add .
git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M:%S')" || echo "No changes to commit"
git push origin main

# Deploy on remote server
echo "🔗 Deploying on Pi4-2..."
ssh $REMOTE_USER@$REMOTE_HOST << 'ENDSSH'
set -e

# Navigate to app directory
cd /home/lexun/ai-consultant || { echo "Creating directory..."; mkdir -p /home/lexun/ai-consultant; cd /home/lexun/ai-consultant; }

# Pull latest changes
if [ -d ".git" ]; then
    echo "Pulling latest changes..."
    git pull origin main
else
    echo "Cloning repository..."
    git clone git@NTMY:stepun/ai-consultant.git .
fi

# Copy environment file if not exists
if [ ! -f ".env" ]; then
    echo "⚠️  Please create .env file from .env.example and configure it!"
    cp .env.example .env
fi

# Setup SSL certificates with Let's Encrypt
if [ ! -d "config/ssl" ]; then
    echo "🔐 Setting up SSL certificates..."
    sudo apt-get update
    sudo apt-get install -y certbot

    # Stop nginx if running
    sudo systemctl stop nginx 2>/dev/null || true

    # Generate certificate
    sudo certbot certonly --standalone \
        --email stepun@gmail.com \
        --agree-tos \
        --no-eff-email \
        -d consultant.sh3.su

    # Create ssl directory and copy certificates
    mkdir -p config/ssl
    sudo cp /etc/letsencrypt/live/consultant.sh3.su/fullchain.pem config/ssl/
    sudo cp /etc/letsencrypt/live/consultant.sh3.su/privkey.pem config/ssl/
    sudo chown -R $USER:$USER config/ssl
fi

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

# Build and start containers
echo "🔨 Building and starting containers..."
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
echo "🔍 Checking service status..."
docker compose -f docker-compose.prod.yml ps

# Setup cron for SSL renewal
echo "🔄 Setting up SSL renewal cron..."
(crontab -l 2>/dev/null; echo "0 2 * * * certbot renew --quiet && docker compose -f /home/lexun/ai-consultant/docker-compose.prod.yml restart nginx") | crontab -

echo "✅ Deployment completed successfully!"
echo "📊 Service status:"
docker compose -f docker-compose.prod.yml logs --tail=20

ENDSSH

echo "🎉 Deployment to Pi4-2 completed!"
echo "🌐 Bot should be available at: https://consultant.sh3.su"