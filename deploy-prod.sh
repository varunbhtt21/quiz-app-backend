#!/bin/bash

echo "🚀 Starting Production Deployment..."
echo "📁 Using: docker-compose.prod.yml"
echo "⚡ Production Server: Gunicorn + 2 Uvicorn Workers"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "📝 Please create .env file with production configuration"
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

# Validate production environment variables using actual .env variable names
echo "🔍 Validating production environment..."

if [ -z "$CORS_ORIGINS" ]; then
    echo "⚠️  Warning: CORS_ORIGINS not set in .env"
fi

if [ -z "$JWT_SECRET_KEY" ]; then
    echo "❌ Error: JWT_SECRET_KEY must be set for production!"
    exit 1
fi

if [ "$DEBUG" = "True" ]; then
    echo "⚠️  Warning: DEBUG is set to True in production!"
fi

if [ -z "$SUPABASE_URL" ]; then
    echo "⚠️  Warning: SUPABASE_URL not set in .env"
fi

if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL must be set for production!"
    exit 1
fi

# Pull latest images (if using registry)
echo "📥 Pulling latest images..."
docker-compose -f docker-compose.prod.yml pull || echo "ℹ️  No registry images to pull"

# Build and start services with production config
echo "🔨 Building and starting production services..."
echo "🏭 Server Configuration: Gunicorn with 2 Uvicorn workers"
docker-compose -f docker-compose.prod.yml up --build -d

# Wait for services to start
sleep 10

# Check service status
echo "🔍 Checking service status..."
docker-compose -f docker-compose.prod.yml ps

# Health check with retries
echo "🏥 Production health check..."
for i in {1..5}; do
    if curl -f "$HEALTH_CHECK_URL" >/dev/null 2>&1; then
        echo "✅ Backend is healthy!"
        break
    else
        echo "⏳ Health check attempt $i/5 failed, retrying..."
        sleep 5
    fi
done

# Show final status
echo "🎉 Production deployment completed!"
echo "🔧 Backend API: $BACKEND_URL"
echo "📚 API Docs: $BACKEND_URL/docs"
echo "⚡ Server: Gunicorn + 2 Uvicorn Workers (Production Optimized)"

echo ""
echo "📋 Production management commands:"
echo "  docker-compose -f docker-compose.prod.yml logs -f     # View logs"
echo "  docker-compose -f docker-compose.prod.yml down       # Stop services"
echo "  docker-compose -f docker-compose.prod.yml restart    # Restart services"
echo "  docker-compose -f docker-compose.prod.yml ps         # Check status"

echo ""
echo "🔒 Security reminders:"
echo "  - Ensure firewall is configured"
echo "  - SSL certificates are installed"
echo "  - Monitoring is active" 