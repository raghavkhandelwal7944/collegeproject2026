#!/bin/bash

# Exit on error
set -e

echo ">>> Checking Prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "Error: npm could not be found."
    exit 1
fi

echo ">>> Setting up Python Backend..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing backend dependencies..."
pip install -r requirements.txt

echo ">>> Setting up React Frontend..."
cd frontend-react
if [ ! -d "node_modules" ]; then
    echo "Installing node modules..."
    npm install
fi

echo ">>> Starting Services..."

# Start Backend in background
cd ..
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend running on http://localhost:8000 (PID: $BACKEND_PID)"

# Start Frontend
echo "Starting Frontend..."
cd frontend-react
npm run dev

# Cleanup
kill $BACKEND_PID
echo "Services stopped."
