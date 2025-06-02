#!/bin/bash

echo "🚀 Starting Development Deployment..."
echo "📁 Using: docker-compose.yml"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Please create .env file with your configuration"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Use actual environment variables from .env
# Backend defaults (Docker container runs on port 8000)
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
HEALTH_CHECK_URL=${HEALTH_CHECK_URL:-http://localhost:8000/health}

# Frontend URL from .env (user has FRONTEND_URL=http://localhost:8080)
FRONTEND_DISPLAY_URL=${FRONTEND_URL:-http://localhost:8080}

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up --build -d

# Wait a moment for services to start
sleep 5

# Check service status
echo "🔍 Checking service status..."
docker-compose ps

# Show health status
echo "🏥 Health check..."
sleep 10
curl -f "$HEALTH_CHECK_URL" && echo "✅ Backend is healthy!" || echo "❌ Backend health check failed"

echo "🎉 Development deployment completed!"
echo "📱 Frontend: $FRONTEND_DISPLAY_URL"
echo "🔧 Backend API: $BACKEND_URL"
echo "📚 API Docs: $BACKEND_URL/docs"

echo ""
echo "📋 Useful commands:"
echo "  docker-compose logs -f          # View logs"
echo "  docker-compose down            # Stop services"
echo "  docker-compose restart         # Restart services" 