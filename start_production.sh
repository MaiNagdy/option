#!/bin/bash

# Production Start Script for Option Analytics

echo "=========================================="
echo "🚀 Starting Production Server"
echo "=========================================="

# Set production environment variables
export APP_ENV=production
export HOST=0.0.0.0
export PORT=8000
export DEBUG=False
export ALLOWED_HOSTS=*
export CORS_ORIGINS=*

# Generate a random secret key if not set
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "✅ Generated new SECRET_KEY"
fi

echo ""
echo "🌐 Server will be accessible at:"
echo "   - Local: http://localhost:8000"
echo "   - Network: http://$(hostname -I | awk '{print $1}'):8000"
echo "   - External: http://YOUR_PUBLIC_IP:8000"
echo ""
echo "✅ All features enabled:"
echo "   - Full Profile Access"
echo "   - Unlimited Analysis"
echo "   - CSV Export"
echo "   - All Valuation Models"
echo ""
echo "=========================================="
echo ""

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "📦 Installing dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start the application
python app.py

