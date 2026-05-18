#!/bin/bash
# AS Updates - Quick Start Script
# This script sets up and runs the AS Updates Flask application

set -e

echo "=================================="
echo "🚀 AS Updates - Quick Start"
echo "=================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

echo "✓ Python 3 found"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed"
    exit 1
fi

echo "✓ pip3 found"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -q Flask==3.0.0
pip3 install -q Flask-Session==0.5.0
pip3 install -q APScheduler==3.10.4
pip3 install -q python-dotenv==1.0.0
pip3 install -q Werkzeug==3.0.0
pip3 install -q pytz==2024.1
echo "✓ Dependencies installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 .env file not found"
    if [ -f .env.example ]; then
        echo "📋 Creating .env from .env.example..."
        cp .env.example .env
        echo "✓ .env created"
        echo ""
        echo "⚠️  IMPORTANT: Edit .env and set:"
        echo "   - ADMIN_PASSWORD: Change to your password"
        echo "   - GMAIL_USER: (optional for email)"
        echo "   - GMAIL_APP_PASSWORD: (optional for email)"
        echo ""
        echo "Then run this script again or start the app with:"
        echo "   python3 app.py"
        exit 0
    else
        echo "❌ .env.example not found"
        exit 1
    fi
else
    echo "✓ .env file found"
fi

echo ""
echo "=================================="
echo "🎯 Starting AS Updates"
echo "=================================="
echo ""
echo "📍 Access the app at: http://localhost:5000"
echo ""
echo "🔐 Admin Password: (check your .env file)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the Flask app
python3 app.py
