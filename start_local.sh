#!/bin/bash
# Local development startup script
# Runs bot in polling mode with optional SSH tunnel

echo "🚀 Starting Bot Oracle in LOCAL MODE"
echo ""

# Load environment variables
source .env 2>/dev/null || true

# Check if SSH tunnel is needed
if [ -n "$USE_SSH_TUNNEL" ]; then
    echo "📡 Creating SSH tunnel to remote database..."

    # Kill existing SSH tunnel if any
    pkill -f "ssh.*5433:localhost:5432.*Pi4-2" 2>/dev/null
    sleep 1

    # Create SSH tunnel to database (background)
    ssh -f -N -L 5433:localhost:5432 Pi4-2
    sleep 2

    if ! pgrep -f "ssh.*5433:localhost:5432.*Pi4-2" > /dev/null; then
        echo "❌ Failed to create SSH tunnel"
        exit 1
    fi

    echo "✅ SSH tunnel created (localhost:5433 -> Pi4-2:5432)"
    echo ""
else
    echo "📡 Using local database (no SSH tunnel)"
    echo ""
fi

# Run the bot
echo "🤖 Starting bot in polling mode..."
python3 run_local.py

# Cleanup on exit
if [ -n "$USE_SSH_TUNNEL" ]; then
    echo ""
    echo "🧹 Cleaning up SSH tunnel..."
    pkill -f "ssh.*5433:localhost:5432.*Pi4-2"
    echo "✅ Done"
fi