#!/bin/bash
# Quick setup script for Narrator Docker development environment

set -e  # Exit on error

echo "🚀 Setting up Narrator Docker development environment..."

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

# Start PostgreSQL container
echo "📦 Starting PostgreSQL container..."
if docker compose version &> /dev/null 2>&1; then
    docker compose up -d
else
    docker-compose up -d
fi

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec narrator-postgres pg_isready -U narrator &> /dev/null; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL failed to start after 30 seconds"
        exit 1
    fi
    sleep 1
done

# Initialize database tables
echo "🔧 Initializing database tables..."
export NARRATOR_DATABASE_URL="postgresql+asyncpg://narrator:narrator_dev@localhost:5432/narrator"

if command -v uv &> /dev/null; then
    echo "Using uv to run narrator..."
    uv run narrator init
    echo "✅ Database tables created successfully!"
    
    # Show status
    echo ""
    echo "📊 Database status:"
    uv run narrator status
elif command -v narrator &> /dev/null; then
    narrator init
    echo "✅ Database tables created successfully!"
    
    # Show status
    echo ""
    echo "📊 Database status:"
    narrator status
else
    echo "⚠️  narrator command not found. Please install narrator first:"
    echo "    uv add slide-narrator"
    echo ""
    echo "Then run: uv run narrator init --database-url \"$NARRATOR_DATABASE_URL\""
fi

echo ""
echo "🎉 Setup complete! Your database is ready at:"
echo "   postgresql+asyncpg://narrator:narrator_dev@localhost:5432/narrator"
echo ""
echo "To stop the container: docker-compose down"
echo "To remove all data: docker-compose down -v"
