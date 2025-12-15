#!/bin/bash
# Quick start script for SDASystem

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       SDASystem v0.1 - Quick Start                        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
if [ ! -f "venv/.installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    touch venv/.installed
fi

echo "Note: Mock-data generation is NOT part of the default startup anymore."
echo "If you need mock data, run: python scripts/generate_mock_data.py --force"

echo "[run] Backend (serves frontend static) → http://localhost:8000/ui"
echo "[run] API docs → http://localhost:8000/docs"
echo "[run] Stop: Ctrl+C"
echo ""

# Start the server with reload
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
