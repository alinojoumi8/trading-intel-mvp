#!/bin/bash
# Restore Trading Intelligence Platform on a new machine
# Usage: ./restore.sh <path-to-archive.tar.gz>

set -e

if [ -z "$1" ]; then
  echo "Usage: ./restore.sh <path-to-archive.tar.gz>"
  exit 1
fi

ARCHIVE="$1"
PROJECT_DIR="$HOME/projects/trading-intel-mvp"

echo "Restoring Trading Intelligence Platform..."
echo "  Archive: $ARCHIVE"
echo "  Target:  $PROJECT_DIR"
echo ""

# Extract
mkdir -p "$PROJECT_DIR"
tar -xzf "$ARCHIVE" -C "$PROJECT_DIR"
echo "Archive extracted."

# Install backend dependencies
echo ""
echo "Installing backend dependencies..."
cd "$PROJECT_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
pip install -q -e . 2>/dev/null || true

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd "$PROJECT_DIR/frontend"
npm install

echo ""
echo "============================================"
echo "Restore complete!"
echo ""
echo "Next steps:"
echo "  1. Add your API keys to: $PROJECT_DIR/backend/.env"
echo "     (copy from your backup .env file)"
echo ""
echo "  2. Seed the database:"
echo "     cd $PROJECT_DIR/backend"
echo "     source venv/bin/activate"
echo "     python seed.py"
echo ""
echo "  3. Start the platform:"
echo "     cd $PROJECT_DIR"
echo "     ./run.sh start"
echo ""
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000/docs"
echo "============================================"
