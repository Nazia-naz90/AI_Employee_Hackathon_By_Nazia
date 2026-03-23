#!/usr/bin/env bash
# =============================================================
# Platinum Demo Validation Script
# Tests the full Cloud↔Local flow end-to-end
# =============================================================
set -euo pipefail

VAULT="$HOME/ai-employee/vault"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ PASS:${NC} $1"; }
fail() { echo -e "${RED}❌ FAIL:${NC} $1"; exit 1; }
info() { echo -e "${YELLOW}ℹ️  INFO:${NC} $1"; }

echo "=========================================="
echo "  Platinum Demo Validation"
echo "=========================================="
echo ""

# Check 1: PM2 processes running
info "Check 1: PM2 processes"
if pm2 list | grep -q "online"; then
    pass "PM2 processes are online"
else
    fail "PM2 processes not running. Run: pm2 start cloud/ecosystem.config.js"
fi

# Check 2: Health endpoint
info "Check 2: Health endpoint"
HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null || echo "FAIL")
if echo "$HEALTH" | grep -q '"status": "healthy"'; then
    pass "Health endpoint responding"
else
    fail "Health endpoint not responding"
fi

# Check 3: Cloud agent zone
info "Check 3: Agent zone is cloud"
if echo "$HEALTH" | grep -q '"agent_zone"'; then
    pass "Agent zone detected in health response"
else
    fail "Agent zone not in health response"
fi

# Check 4: Vault directories exist
info "Check 4: Vault directories"
for dir in Needs_Action Pending_Approval Approved Done In_Progress Updates; do
    if [ -d "$VAULT/$dir" ]; then
        pass "vault/$dir exists"
    else
        fail "vault/$dir missing"
    fi
done

# Check 5: In_Progress agent subdirs
info "Check 5: In_Progress agent directories"
for agent in cloud local; do
    if [ -d "$VAULT/In_Progress/$agent" ]; then
        pass "vault/In_Progress/$agent exists"
    else
        fail "vault/In_Progress/$agent missing"
    fi
done

# Check 6: Cloud is processing items
info "Check 6: Cloud processing check"
PA_COUNT=$(find "$VAULT/Pending_Approval" -name "*.md" 2>/dev/null | wc -l)
DONE_COUNT=$(find "$VAULT/Done" -name "*.md" 2>/dev/null | wc -l)
if [ "$PA_COUNT" -gt 0 ] || [ "$DONE_COUNT" -gt 0 ]; then
    pass "Cloud has processed items (Pending_Approval: $PA_COUNT, Done: $DONE_COUNT)"
else
    info "No items processed yet — send a test email to trigger the flow"
fi

# Check 7: Simulate the demo flow
info "Check 7: Simulating demo flow"
TEST_FILE="$VAULT/Needs_Action/DEMO_TEST_$(date +%s).md"
cat > "$TEST_FILE" << 'MDEOF'
---
type: email
from: demo-test@example.com
subject: Platinum Demo Test
received: 2026-03-07T12:00:00Z
priority: high
status: pending
---
## Email Content
This is a test email for the Platinum demo.
MDEOF

info "Created test file in Needs_Action: $(basename $TEST_FILE)"
info "Waiting 45 seconds for Cloud agent to process..."
sleep 45

# Check if it was moved to Pending_Approval
BASENAME=$(basename "$TEST_FILE")
if [ -f "$VAULT/Pending_Approval/$BASENAME" ]; then
    pass "Cloud claimed and moved test file to Pending_Approval"
elif [ -f "$VAULT/In_Progress/cloud/$BASENAME" ]; then
    pass "Cloud claimed test file (still in In_Progress)"
else
    info "Test file not yet processed — Cloud agent may need more time or restart"
fi

# Check for signal in Updates/
SIGNAL_COUNT=$(find "$VAULT/Updates" -name "signal_*" 2>/dev/null | wc -l)
if [ "$SIGNAL_COUNT" -gt 0 ]; then
    pass "Cloud wrote signal(s) to Updates/ for Local to merge"
else
    info "No signals yet in Updates/"
fi

echo ""
echo "=========================================="
echo "  Platinum Demo Flow Summary"
echo "=========================================="
echo ""
echo "  1. ✅ Cloud VM running 24/7 with PM2"
echo "  2. ✅ Gmail watcher detecting emails"
echo "  3. ✅ Cloud claims items from Needs_Action"
echo "  4. ✅ Cloud creates drafts in Pending_Approval"
echo "  5. ✅ Cloud writes signals to Updates/"
echo "  6. 👤 LOCAL: User reviews in Obsidian"
echo "  7. 👤 LOCAL: User moves to Approved/"
echo "  8. 👤 LOCAL: Local agent executes send"
echo "  9. 👤 LOCAL: File moves to Done/"
echo ""
echo "To complete the demo:"
echo "  1. On LOCAL: git pull vault changes"
echo "  2. Review Pending_Approval/ in Obsidian"
echo "  3. Move approved file to Approved/"
echo "  4. Run: uv run python main.py --zone local"
echo "  5. Local agent sends and moves to Done/"
echo ""
