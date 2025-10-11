#!/bin/bash

echo "🚀 Verifying Blockchain Financial Platform Setup"
echo "================================================"

# Check Go installation
echo "📋 Checking Go installation..."
if command -v go &> /dev/null; then
    echo "✅ Go is installed: $(go version)"
else
    echo "❌ Go is not installed"
    exit 1
fi

# Check Python installation
echo "📋 Checking Python installation..."
if command -v python3 &> /dev/null; then
    echo "✅ Python is installed: $(python3 --version)"
else
    echo "❌ Python is not installed"
    exit 1
fi

# Check Docker installation
echo "📋 Checking Docker installation..."
if command -v docker &> /dev/null; then
    echo "✅ Docker is installed: $(docker --version)"
else
    echo "❌ Docker is not installed"
    exit 1
fi

# Test Go chaincode modules
echo "📋 Testing Go chaincode modules..."
cd fabric-chaincode/shared
if go test -v > /dev/null 2>&1; then
    echo "✅ Go chaincode tests pass"
else
    echo "❌ Go chaincode tests failed"
    exit 1
fi
cd ../..

# Test Python backend
echo "📋 Testing Python backend..."
cd backend
if [ -d "venv" ]; then
    source venv/bin/activate
    if pytest tests/test_main.py -v > /dev/null 2>&1; then
        echo "✅ Python backend tests pass"
    else
        echo "❌ Python backend tests failed"
        exit 1
    fi
    deactivate
else
    echo "⚠️  Python virtual environment not found. Run: cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
fi
cd ..

echo ""
echo "🎉 Setup verification complete!"
echo ""
echo "Next steps:"
echo "1. Start the development environment: docker-compose up -d"
echo "2. Deploy chaincode: cd fabric-chaincode && ./scripts/deploy-chaincode.sh"
echo "3. Start the backend API: cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs will be available at: http://localhost:8000/docs"