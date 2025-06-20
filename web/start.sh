#!/bin/bash

# Branch Cleaner Web UI Startup Script
# This script starts both the backend API server and the frontend development server

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Branch Cleaner Web UI${NC}"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Not in a git repository${NC}"
    echo "Please run this script from within a git repository"
    exit 1
fi

# Store the current working directory (the git repository)
REPO_DIR="$(pwd)"
echo -e "${BLUE}📁 Repository directory: $REPO_DIR${NC}"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ Error: GitHub CLI (gh) is not installed${NC}"
    echo "Please install it from: https://cli.github.com/"
    exit 1
fi

# Check if gh is authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}❌ Error: Not authenticated with GitHub${NC}"
    echo "Please run: gh auth login"
    exit 1
fi



# Function to kill background processes on exit
cleanup() {
    echo -e "\n${BLUE}🛑 Shutting down services...${NC}"
    jobs -p | xargs -r kill 2>/dev/null || true
    wait
    echo -e "${GREEN}✅ Services stopped${NC}"
}

trap cleanup EXIT INT TERM

# Start the backend server
echo -e "${BLUE}📡 Starting backend server...${NC}"
cd "$SCRIPT_DIR/backend"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install -q -r requirements.txt

# Start the backend server in the background with the repo directory
export GIT_REPO_PATH="$REPO_DIR"
python "$SCRIPT_DIR/backend/app.py" &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend server started${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Backend server failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Start the frontend server
echo -e "${BLUE}🎨 Starting frontend server...${NC}"
cd "$SCRIPT_DIR/frontend"

# Install frontend dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start the frontend server
echo -e "${GREEN}✅ Starting frontend development server...${NC}"
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
echo "Waiting for frontend to start..."
for i in {1..30}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Frontend server started${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Frontend server failed to start${NC}"
        exit 1
    fi
    sleep 1
done

echo -e "\n${GREEN}🎉 Branch Cleaner Web UI is running!${NC}"
echo -e "${BLUE}📍 Open http://localhost:3000 in your browser${NC}"
echo -e "\nPress Ctrl+C to stop all services\n"

# Wait for background processes
wait
