#!/bin/bash
# Backup my memory (Hermes agent memories + skills)
# Usage: ./backup_memory.sh

set -e

BACKUP_DIR="$HOME/backups/hermes-memory"
DATE=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="hermes-memory_${DATE}.tar.gz"

mkdir -p "$BACKUP_DIR"

# Backup memories (the core 12KB files)
tar -czf "${BACKUP_DIR}/memories_${DATE}.tar.gz" \
    -C "$HOME/.hermes/memories" .

# Backup skills (read-only reference — these don't change often)
tar -czf "${BACKUP_DIR}/skills_${DATE}.tar.gz" \
    --exclude='.git' \
    -C "$HOME/.hermes/skills" .

# Backup config (just the relevant parts — not full config with keys)
grep -E "^(model:|provider:|base_url:)" \
    "$HOME/.hermes/config.yaml" > "${BACKUP_DIR}/model_config_${DATE}.txt" 2>/dev/null || true

echo "Memory backup created:"
echo "  Memories: ${BACKUP_DIR}/memories_${DATE}.tar.gz"
echo "  Skills:   ${BACKUP_DIR}/skills_${DATE}.tar.gz"
echo "  Config:   ${BACKUP_DIR}/model_config_${DATE}.txt"
echo ""

# List the actual memories for visibility
echo "Current memories (what gets backed up):"
echo "=== MEMORY.md ==="
cat "$HOME/.hermes/memories/MEMORY.md"
echo ""
echo "=== USER.md ==="
cat "$HOME/.hermes/memories/USER.md"
