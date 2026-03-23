#!/usr/bin/env bash
set -euo pipefail
VAULT_DIR="${VAULT_DIR:-$HOME/ai-employee/vault}"
LOG_FILE="${VAULT_DIR}/Logs/vault_sync.log"
LOCK_FILE="/tmp/vault_sync.lock"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG_FILE"; }

if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log "SKIP: Another sync running (PID $LOCK_PID)"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$VAULT_DIR"

log "Pulling from remote..."
git fetch origin main 2>&1 | tee -a "$LOG_FILE" || true

if ! git merge origin/main --no-edit 2>&1 | tee -a "$LOG_FILE"; then
    log "ERROR: Merge conflict — using theirs (Local is authority)"
    git checkout --theirs . 2>/dev/null || true
    git add .
    git commit -m "auto-merge: resolved conflict (prefer local)" 2>&1 | tee -a "$LOG_FILE" || true
fi

if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "cloud-sync: $(date -u +%Y-%m-%dT%H:%M:%SZ)" 2>&1 | tee -a "$LOG_FILE"
    git push origin main 2>&1 | tee -a "$LOG_FILE"
    log "Pushed Cloud changes"
else
    log "No changes to push"
fi

log "Sync complete"
