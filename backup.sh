#!/bin/bash
# Backup the Trading Intelligence Platform to a portable archive
# Excludes node_modules and venv (regenerate with pip/npm install)
# Usage: ./backup.sh

set -e

PROJECT_DIR="$HOME/projects/trading-intel-mvp"
BACKUP_DIR="$HOME/backups/trading-intel-mvp"
DATE=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="trading-intel-mvp_${DATE}.tar.gz"

echo "Creating backup..."
mkdir -p "$BACKUP_DIR"

# Create tar.gz excluding node_modules, venv, __pycache__, .git, *.log
tar --exclude='node_modules' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='*.pyc' \
    --exclude='trading_intel.db' \
    -czf "${BACKUP_DIR}/${ARCHIVE_NAME}" \
    -C "$PROJECT_DIR" .

echo ""
echo "Backup created: ${BACKUP_DIR}/${ARCHIVE_NAME}"
echo "Size: $(du -sh "${BACKUP_DIR}/${ARCHIVE_NAME}" | cut -f1)"
echo ""

# Also save the API keys / .env
ENV_BACKUP="${BACKUP_DIR}/.env_backup_${DATE}"
grep -E "MINIMAX_API_KEY|ALPHA_VANTAGE_API_KEY|FINNHUB_API_KEY|NEWSAPI_KEY" \
    "$PROJECT_DIR/backend/.env" > "$ENV_BACKUP" 2>/dev/null || true

echo "API keys backed up to: $ENV_BACKUP"
echo "IMPORTANT: Copy this file separately and delete after restoring keys!"
echo ""
echo "To restore on a new machine:"
echo "  1. Copy the archive to the new machine"
echo "  2. tar -xzf trading-intel-mvp_YYYYMMDD_HHMMSS.tar.gz -C ~/projects/"
echo "  3. cd ~/projects/trading-intel-mvp/backend && pip install -r requirements.txt && source venv/bin/activate && pip install -e."
echo "  4. cd ~/projects/trading-intel-mvp/frontend && npm install"
echo "  5. Restore your .env with API keys"
echo "  6. ./run.sh start"
