#!/bin/bash
# Local development setup script

set -e

echo "🚀 Setting up Third Eye Chatbot for local development..."

# Check Python version
echo "📌 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "❌ Python 3.11+ is required. Current version: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo "🛠️  Installing development dependencies..."
pip install black isort flake8 pytest pytest-asyncio pytest-cov

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env with your Azure credentials"
fi

# Check for Redis
echo "🔍 Checking for Redis..."
if ! command -v redis-cli &> /dev/null; then
    echo "⚠️  Redis not found. Starting Redis with Docker..."
    docker run -d -p 6379:6379 --name third-eye-redis redis:7-alpine
else
    echo "✅ Redis is available"
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x scripts/*.sh
chmod +x scripts/*.py

echo ""
echo "✨ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Update .env with your Azure credentials"
echo "  2. Run 'make dev' to start the API server"
echo "  3. Run 'make worker' in another terminal to start the Celery worker"
echo "  4. Run 'make seed' to populate the knowledge base"
echo "  5. Visit http://localhost:8000 to use the chatbot"
echo ""
echo "💡 Useful commands:"
echo "  make dev      - Start development server"
echo "  make worker   - Start Celery worker"
echo "  make test     - Run tests"
echo "  make lint     - Run linting"
echo "  make format   - Format code"
echo ""