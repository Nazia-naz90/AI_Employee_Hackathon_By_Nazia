---
name: platinum-cloud-deploy
description: >
  Deploy the Personal AI Employee project to an Oracle Cloud VM for Platinum Tier.
  This skill sets up the complete Cloud↔Local architecture including: cloning the project,
  installing all dependencies, creating Platinum-specific Python files (agent_role.py,
  cloud_orchestrator.py, cloud_main.py, health_monitor.py), configuring PM2 for 24/7 operation,
  setting up Odoo via Docker, configuring vault Git sync, and opening firewall ports.
  Use this skill when the user says "deploy to cloud", "set up platinum tier", "configure oracle VM",
  "cloud deployment", or anything related to getting the AI Employee running on a remote server.
  This skill requires SSH access to the target VM.
---

# Platinum Cloud Deployment Skill

## Overview

This skill deploys the Personal AI Employee (Gold Tier) to an Oracle Cloud VM,
transforming it into a Platinum Tier system with Cloud↔Local work-zone specialization.

**What this skill does:**
1. Connects to Oracle Cloud VM via SSH
2. Installs all system dependencies
3. Clones the project from GitHub
4. Copies local secrets (`.env`, `credentials.json`, `token.json`) to the VM
5. Creates all Platinum-specific Python files
6. Configures PM2 for 24/7 process management
7. Deploys Odoo via Docker
8. Sets up vault Git sync between Cloud and Local
9. Updates main.py with `--zone` flag for Local orchestrator
10. Configures HTTPS for Odoo via Caddy reverse proxy
11. Runs Platinum demo validation test
12. Updates README.md with Platinum tier declaration
13. Creates `skills/platinum-cloud/SKILL.md` project skill
14. Configures firewall and health monitoring
15. Hardens SSH and enables auto-updates
16. Validates the entire deployment

**Architecture being deployed:**
```
┌──────────────────────────┬──────────────────────────────────────┐
│      CLOUD VM (24/7)     │           LOCAL (User's PC)          │
│                          │                                       │
│  ✅ Gmail Watcher        │  ✅ Approvals (move files)           │
│  ✅ Facebook Watcher     │  ✅ WhatsApp Watcher (session)       │
│  ✅ LinkedIn Watcher     │  ✅ Payment execution                │
│  ✅ Twitter Watcher      │  ✅ Final send/post actions          │
│  ✅ Email triage/draft   │  ✅ Dashboard.md (single-writer)     │
│  ✅ Social post drafts   │                                       │
│  ✅ CEO Briefing gen     │  🔒 ALL secrets stay here            │
│  ✅ Odoo (draft-only)    │                                       │
│                          │                                       │
│  vault/ ◄──── Git ────► vault/                                  │
└──────────────────────────┴──────────────────────────────────────┘
```

---

## Prerequisites

Before running this skill, confirm the following with the user:

1. **Oracle Cloud VM is created and running** (Ubuntu 22.04 or 24.04)
2. **SSH private key file** is available locally
3. **VM public IP address** is known
4. **Project is pushed to GitHub** (with secrets excluded via .gitignore)
5. **GitHub Personal Access Token** is available (if repo is private)

Ask the user for these values before proceeding:
- `VM_IP`: The public IP of the Oracle VM
- `SSH_KEY_PATH`: Local path to the SSH private key (e.g., `C:\Users\PMLS\Downloads\ssh-key-2026-03-05.key`)
- `SSH_USER`: Usually `ubuntu` for Ubuntu images
- `GITHUB_REPO`: The GitHub repo URL (e.g., `https://github.com/username/ai-employee-hackathon.git`)
- `LOCAL_PROJECT_PATH`: Local path to the project (e.g., `C:\Users\PMLS\Desktop\...\AI_Employee_Hackathon`)

---

## PHASE 1: System Setup (Run via SSH on the VM)

### Step 1.1: Connect to the VM

```bash
ssh -o ServerAliveInterval=60 -i <SSH_KEY_PATH> <SSH_USER>@<VM_IP>
```

> **IMPORTANT:** Use `-o ServerAliveInterval=60` to prevent disconnects.

### Step 1.2: Update system packages

```bash
sudo apt-get update -y && sudo apt-get upgrade -y
```

### Step 1.3: Install core dependencies

```bash
sudo apt-get install -y python3-pip python3-venv git docker.io docker-compose-v2 curl unzip
```

### Step 1.4: Install uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

> **VERIFY:** Run `uv --version` — should output a version number.

### Step 1.5: Install Node.js 22.x

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

> **VERIFY:** Run `node --version` — should output v22.x.x

### Step 1.6: Install PM2 (process manager)

```bash
sudo npm install -g pm2
```

> **VERIFY:** Run `pm2 --version` — should output a version number.

### Step 1.7: Configure Docker

```bash
sudo usermod -aG docker $USER
sudo systemctl enable docker
sudo systemctl start docker
```

> **NOTE:** Docker group changes require re-login. For current session, prefix docker commands with `sudo`.

### Step 1.8: Install Playwright browser dependencies

```bash
sudo apt-get install -y libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
  libpango-1.0-0 libasound2t64 libxfixes3 libxext6 libxi6 libxrender1 libxtst6
```

> **NOTE:** Package names ending in `t64` are for Ubuntu 24.04. On Ubuntu 22.04,
> remove the `t64` suffix (e.g., `libatk1.0-0` instead of `libatk1.0-0t64`).
> If any package is not found, skip it and continue.

---

## PHASE 2: Project Setup (Run via SSH on the VM)

### Step 2.1: Create project directory and clone

```bash
mkdir -p ~/ai-employee
cd ~/ai-employee
git clone <GITHUB_REPO> .
```

> If the repo is private, git will ask for credentials.
> Use the GitHub username and a Personal Access Token as password.
> If clone creates a subfolder, move contents up:
> ```bash
> mv <repo-name>/* <repo-name>/.* . 2>/dev/null; rm -rf <repo-name>
> ```

### Step 2.2: Install Python dependencies

```bash
cd ~/ai-employee
uv sync
```

> **VERIFY:** Should complete without errors and create a `.venv` directory.

### Step 2.3: Install Playwright Chromium

```bash
uv run playwright install chromium
```

> **VERIFY:** Should download chromium and ffmpeg successfully.

### Step 2.4: Copy secrets from local machine

**CRITICAL: Do NOT create these files manually. Copy them from the user's local machine.**

Run these commands from the **LOCAL machine** (not the VM). Open a NEW terminal/PowerShell:

```bash
scp -i <SSH_KEY_PATH> "<LOCAL_PROJECT_PATH>/config/.env" <SSH_USER>@<VM_IP>:~/ai-employee/config/.env
scp -i <SSH_KEY_PATH> "<LOCAL_PROJECT_PATH>/config/credentials.json" <SSH_USER>@<VM_IP>:~/ai-employee/config/credentials.json
scp -i <SSH_KEY_PATH> "<LOCAL_PROJECT_PATH>/config/token.json" <SSH_USER>@<VM_IP>:~/ai-employee/config/token.json
```

> **IMPORTANT:** These are the REAL secrets from the user's local machine.
> Never generate fake .env files. Always copy the actual files.
> Session folders (whatsapp_session, meta_session, etc.) should NOT be copied — they stay local only.

### Step 2.5: Add AGENT_ZONE to .env

Back on the VM via SSH:

```bash
echo "" >> ~/ai-employee/config/.env
echo "# === PLATINUM: Cloud Agent Zone ===" >> ~/ai-employee/config/.env
echo "AGENT_ZONE=cloud" >> ~/ai-employee/config/.env
```

### Step 2.6: Verify project imports

```bash
cd ~/ai-employee
uv run python -c "from backend.orchestrator.orchestrator import Orchestrator; print('Import OK')"
```

> **MUST OUTPUT:** `Import OK`
> If it fails, check that all dependencies are installed and the project structure is correct.

### Step 2.7: Run tests

```bash
cd ~/ai-employee
uv run pytest tests/ -v --tb=short 2>&1 | tail -5
```

> **VERIFY:** All tests should pass. The last line should show something like `606 passed`.

---

## PHASE 3: Create Platinum Python Files (Run via SSH on the VM)

### Step 3.1: Create the cloud module directory

```bash
mkdir -p ~/ai-employee/backend/cloud
touch ~/ai-employee/backend/cloud/__init__.py
```

### Step 3.2: Understand the existing orchestrator structure

**CRITICAL:** Before creating cloud files, you MUST read the existing orchestrator to understand the data structures.

```bash
grep -A 30 "_build_watcher_configs" ~/ai-employee/backend/orchestrator/orchestrator.py
```

**KEY FINDING:** `_build_watcher_configs()` returns a `list[tuple[str, callable]]` where each
item is `(name, factory_function)`. Example: `("Gmail", _gmail_factory)`.

The `_start_watchers()` method iterates as: `for name, factory in watchers_config:`

**You MUST match this tuple format in the cloud orchestrator. Do NOT assume it's a dict.**

Also check how watchers are started:

```bash
grep -B 5 -A 20 "_start_watchers" ~/ai-employee/backend/orchestrator/orchestrator.py | head -40
```

And check the WatcherTask class:

```bash
grep -A 10 "class WatcherTask" ~/ai-employee/backend/orchestrator/watchdog.py
```

### Step 3.3: Create agent_role.py

```bash
cat > ~/ai-employee/backend/cloud/agent_role.py << 'PYEOF'
"""Work-Zone Specialization — determines what each agent (Cloud/Local) owns.

Cloud owns: perception (watchers), triage, drafts, scheduling
Local owns: approvals, WhatsApp session, payments, final execution
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AgentZone(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"


@dataclass(frozen=True)
class ZoneCapabilities:
    can_watch_gmail: bool = False
    can_watch_whatsapp: bool = False
    can_watch_facebook: bool = False
    can_watch_linkedin: bool = False
    can_watch_twitter: bool = False
    can_triage_email: bool = False
    can_draft_replies: bool = False
    can_draft_social_posts: bool = False
    can_generate_briefing: bool = False
    can_run_ralph_loops: bool = False
    can_schedule_content: bool = False
    can_create_draft_actions: bool = False
    can_send_email: bool = False
    can_send_whatsapp: bool = False
    can_post_social: bool = False
    can_execute_payment: bool = False
    can_write_dashboard: bool = False
    can_odoo_read: bool = False
    can_odoo_draft: bool = False
    can_odoo_post: bool = False


CLOUD_CAPABILITIES = ZoneCapabilities(
    can_watch_gmail=True,
    can_watch_whatsapp=False,
    can_watch_facebook=True,
    can_watch_linkedin=True,
    can_watch_twitter=True,
    can_triage_email=True,
    can_draft_replies=True,
    can_draft_social_posts=True,
    can_generate_briefing=True,
    can_run_ralph_loops=True,
    can_schedule_content=True,
    can_create_draft_actions=True,
    can_send_email=False,
    can_send_whatsapp=False,
    can_post_social=False,
    can_execute_payment=False,
    can_write_dashboard=False,
    can_odoo_read=True,
    can_odoo_draft=True,
    can_odoo_post=False,
)

LOCAL_CAPABILITIES = ZoneCapabilities(
    can_watch_gmail=False,
    can_watch_whatsapp=True,
    can_watch_facebook=False,
    can_watch_linkedin=False,
    can_watch_twitter=False,
    can_triage_email=True,
    can_draft_replies=True,
    can_draft_social_posts=False,
    can_generate_briefing=False,
    can_run_ralph_loops=True,
    can_schedule_content=False,
    can_create_draft_actions=True,
    can_send_email=True,
    can_send_whatsapp=True,
    can_post_social=True,
    can_execute_payment=True,
    can_write_dashboard=True,
    can_odoo_read=True,
    can_odoo_draft=True,
    can_odoo_post=True,
)


def get_current_zone() -> AgentZone:
    zone_str = os.getenv("AGENT_ZONE", "local").lower()
    try:
        return AgentZone(zone_str)
    except ValueError:
        return AgentZone.LOCAL


def get_capabilities(zone: AgentZone | None = None) -> ZoneCapabilities:
    if zone is None:
        zone = get_current_zone()
    return CLOUD_CAPABILITIES if zone == AgentZone.CLOUD else LOCAL_CAPABILITIES


@dataclass
class ClaimManager:
    """Implements claim-by-move rule for multi-agent coordination.
    
    First agent to move a file from Needs_Action/ to In_Progress/<agent>/
    owns it. Other agents must ignore files already in In_Progress/.
    """
    vault_path: Path
    agent_name: str

    @property
    def in_progress_dir(self) -> Path:
        return self.vault_path / "In_Progress" / self.agent_name

    def claim(self, source_file: Path) -> Path | None:
        in_progress_root = self.vault_path / "In_Progress"
        if in_progress_root.exists():
            for agent_dir in in_progress_root.iterdir():
                if agent_dir.is_dir():
                    claimed = agent_dir / source_file.name
                    if claimed.exists():
                        return None
        self.in_progress_dir.mkdir(parents=True, exist_ok=True)
        dest = self.in_progress_dir / source_file.name
        try:
            source_file.rename(dest)
            return dest
        except (OSError, FileNotFoundError):
            return None

    def release(self, file_path: Path, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        dest = destination / file_path.name
        file_path.rename(dest)
        return dest

    def list_claimed(self) -> list[Path]:
        if not self.in_progress_dir.exists():
            return []
        return list(self.in_progress_dir.glob("*.md"))
PYEOF
```

> **VERIFY:** `uv run python -c "from backend.cloud.agent_role import AgentZone; print('OK')"`

### Step 3.4: Create cloud_orchestrator.py

**CRITICAL:** This file MUST match the existing orchestrator's `_build_watcher_configs()` return
type which is `list[tuple[str, callable]]`, NOT `list[dict]`. Read Step 3.2 output carefully.

```bash
cat > ~/ai-employee/backend/cloud/cloud_orchestrator.py << 'PYEOF'
"""Cloud Orchestrator — runs 24/7 on the Cloud VM.

Starts only the watchers and reasoning tasks that Cloud is allowed to run.
Writes drafts to Pending_Approval/, Plans/, and Updates/.
Never executes final send/post actions.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.cloud.agent_role import (
    AgentZone,
    ClaimManager,
    get_capabilities,
    get_current_zone,
)
from backend.orchestrator.orchestrator import Orchestrator, OrchestratorConfig
from backend.utils.timestamps import now_iso

logger = logging.getLogger(__name__)


class CloudOrchestrator(Orchestrator):
    """Extended orchestrator that respects Work-Zone boundaries."""

    def __init__(self, config: OrchestratorConfig) -> None:
        super().__init__(config)
        self.zone = get_current_zone()
        self.capabilities = get_capabilities(self.zone)
        self.claim_manager = ClaimManager(
            vault_path=self.vault_path,
            agent_name=self.zone.value,
        )
        (self.vault_path / "In_Progress" / "cloud").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "In_Progress" / "local").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "Updates").mkdir(parents=True, exist_ok=True)

    def _start_watchers(self) -> None:
        """Only start watchers this zone is allowed to run.
        
        IMPORTANT: _build_watcher_configs() returns list[tuple[str, callable]]
        where each item is (name, factory_function). NOT dicts.
        """
        watchers_config = self._build_watcher_configs()
        filtered = []

        for name, factory in watchers_config:
            name_lower = name.lower()
            allowed = False

            if "gmail" in name_lower and self.capabilities.can_watch_gmail:
                allowed = True
            elif "whatsapp" in name_lower and self.capabilities.can_watch_whatsapp:
                allowed = True
            elif "facebook" in name_lower and self.capabilities.can_watch_facebook:
                allowed = True
            elif "linkedin" in name_lower and self.capabilities.can_watch_linkedin:
                allowed = True
            elif "twitter" in name_lower and self.capabilities.can_watch_twitter:
                allowed = True
            elif "vault" in name_lower:
                allowed = True  # Vault watcher runs on all zones

            if allowed:
                filtered.append((name, factory))
            else:
                logger.info(
                    "[%s] Skipping watcher '%s' — not allowed in this zone",
                    self.zone.value,
                    name,
                )

        # Start the filtered watchers using the same logic as parent
        from backend.orchestrator.watchdog import WatcherTask
        for name, factory in filtered:
            try:
                watcher = factory()
                wt = WatcherTask(
                    name=name,
                    watcher=watcher,
                    max_restarts=self.config.max_restart_attempts,
                    log_dir=self.log_dir,
                )
                wt.start()
                self.watcher_tasks.append(wt)
                logger.info("[%s] Started watcher: %s", self.zone.value, name)
            except ImportError as exc:
                logger.warning("[%s] Skipping watcher %s: %s", self.zone.value, name, exc)
            except Exception:
                logger.exception("[%s] Failed to start watcher %s", self.zone.value, name)

        if not self.watcher_tasks:
            logger.warning("[%s] No watchers started", self.zone.value)

    def _start_action_executor(self) -> None:
        """Cloud: only process draft actions. Local: normal execution."""
        if self.zone == AgentZone.CLOUD:
            logger.info("[cloud] Action executor: draft-only mode")
            self._action_executor_task = asyncio.get_event_loop().create_task(
                self._cloud_draft_loop()
            )
        else:
            super()._start_action_executor()

    async def _cloud_draft_loop(self) -> None:
        """Cloud-specific: process Needs_Action items into drafts."""
        while True:
            try:
                needs_action = self.vault_path / "Needs_Action"
                if needs_action.exists():
                    for md_file in sorted(needs_action.glob("*.md")):
                        claimed = self.claim_manager.claim(md_file)
                        if claimed is None:
                            continue
                        logger.info("[cloud] Claimed: %s", md_file.name)
                        await self._process_cloud_item(claimed)
            except Exception:
                logger.exception("[cloud] Error in draft loop")
            await asyncio.sleep(self.config.check_interval)

    async def _process_cloud_item(self, file_path: Path) -> None:
        """Process a claimed item — create signal and move to Pending_Approval."""
        from backend.utils.frontmatter import parse_frontmatter
        try:
            fm = parse_frontmatter(file_path)
            item_type = fm.get("type", "unknown")
            signal_path = (
                self.vault_path / "Updates"
                / f"signal_{now_iso().replace(':', '-')}_{file_path.stem}.md"
            )
            signal_path.write_text(
                f"---\n"
                f"type: cloud_signal\n"
                f"source: {file_path.name}\n"
                f"item_type: {item_type}\n"
                f"timestamp: {now_iso()}\n"
                f"status: drafted\n"
                f"---\n"
                f"Cloud processed {file_path.name} ({item_type})\n",
                encoding="utf-8",
            )
            pending = self.vault_path / "Pending_Approval"
            self.claim_manager.release(file_path, pending)
            logger.info("[cloud] Drafted and moved to Pending_Approval: %s", file_path.name)
        except Exception:
            logger.exception("[cloud] Failed to process: %s", file_path.name)


class LocalOrchestrator(CloudOrchestrator):
    """Local orchestrator — handles approvals, WhatsApp, and final execution.
    Also merges Cloud signals from Updates/ into Dashboard.md.
    """

    async def run(self) -> None:
        asyncio.get_event_loop().create_task(self._merge_updates_loop())
        await super().run()

    async def _merge_updates_loop(self) -> None:
        """Periodically merge Cloud signals from Updates/ into Dashboard.md."""
        while True:
            try:
                updates_dir = self.vault_path / "Updates"
                if updates_dir.exists():
                    signals = sorted(updates_dir.glob("signal_*.md"))
                    if signals:
                        dashboard = self.vault_path / "Dashboard.md"
                        existing = (
                            dashboard.read_text(encoding="utf-8")
                            if dashboard.exists() else ""
                        )
                        new_entries = []
                        for sig in signals:
                            from backend.utils.frontmatter import parse_frontmatter
                            fm = parse_frontmatter(sig)
                            ts = fm.get("timestamp", "?")
                            item = fm.get("item_type", "?")
                            source = fm.get("source", "?")
                            new_entries.append(f"- [{ts}] Cloud processed: {source} ({item})")
                        if new_entries:
                            activity = "\n".join(new_entries)
                            if "## Recent Activity" in existing:
                                existing = existing.replace(
                                    "## Recent Activity",
                                    f"## Recent Activity\n{activity}",
                                )
                            else:
                                existing += f"\n\n## Recent Activity\n{activity}\n"
                            dashboard.write_text(existing, encoding="utf-8")
                        done = self.vault_path / "Done"
                        done.mkdir(parents=True, exist_ok=True)
                        for sig in signals:
                            sig.rename(done / sig.name)
                        logger.info("[local] Merged %d cloud signals into Dashboard", len(signals))
            except Exception:
                logger.exception("[local] Error merging updates")
            await asyncio.sleep(60)
PYEOF
```

> **VERIFY:** `uv run python -c "from backend.cloud.cloud_orchestrator import CloudOrchestrator; print('OK')"`

### Step 3.5: Create cloud/cloud_main.py (Cloud entry point)

```bash
mkdir -p ~/ai-employee/cloud
cat > ~/ai-employee/cloud/cloud_main.py << 'PYEOF'
"""Cloud VM entry point for the AI Employee.

Usage:
    AGENT_ZONE=cloud uv run python cloud/cloud_main.py
    AGENT_ZONE=cloud uv run python cloud/cloud_main.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

os.environ["AGENT_ZONE"] = "cloud"

from backend.cloud.cloud_orchestrator import CloudOrchestrator
from backend.orchestrator.orchestrator import OrchestratorConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Employee — Cloud Agent")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    config = OrchestratorConfig.from_env()

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting AI Employee CLOUD Agent")
    logger.info("DEV_MODE=%s, DRY_RUN=%s, ZONE=cloud", config.dev_mode, config.dry_run)

    orchestrator = CloudOrchestrator(config)
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("Cloud agent stopped by user")


if __name__ == "__main__":
    main()
PYEOF
```

### Step 3.6: Create cloud/health_monitor.py

```bash
cat > ~/ai-employee/cloud/health_monitor.py << 'PYEOF'
"""Health monitor — lightweight HTTP server reporting system status.

Exposes /health endpoint on port 8080 for uptime monitoring.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)

VAULT_PATH = Path(os.getenv("VAULT_PATH", "./vault"))
PORT = int(os.getenv("HEALTH_PORT", "8080"))


def get_health_status() -> dict:
    now = datetime.now(timezone.utc)

    pm2_status = "unknown"
    try:
        result = subprocess.run(
            ["pm2", "jlist"], capture_output=True, text=True, timeout=5
        )
        processes = json.loads(result.stdout)
        pm2_status = {p["name"]: p["pm2_env"]["status"] for p in processes}
    except Exception:
        pm2_status = "pm2 not available"

    folder_counts = {}
    for folder in ["Needs_Action", "Pending_Approval", "Approved", "Done", "In_Progress"]:
        p = VAULT_PATH / folder
        if p.exists():
            folder_counts[folder] = len(list(p.rglob("*.md")))

    return {
        "status": "healthy",
        "timestamp": now.isoformat(),
        "agent_zone": os.getenv("AGENT_ZONE", "unknown"),
        "dev_mode": os.getenv("DEV_MODE", "unknown"),
        "pm2_processes": pm2_status,
        "vault_folders": folder_counts,
    }


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            status = get_health_status()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info("Health monitor running on port %d", PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
PYEOF
```

---

## PHASE 4: PM2 Configuration (Run via SSH on the VM)

### Step 4.1: Create shell wrapper scripts

PM2 cannot run `uv run python` directly as an interpreter. Use shell wrappers instead.

```bash
cat > ~/ai-employee/cloud/start_cloud.sh << 'EOF'
#!/usr/bin/env bash
cd /home/ubuntu/ai-employee
source $HOME/.local/bin/env
AGENT_ZONE=cloud uv run python cloud/cloud_main.py
EOF
chmod +x ~/ai-employee/cloud/start_cloud.sh
```

```bash
cat > ~/ai-employee/cloud/start_health.sh << 'EOF'
#!/usr/bin/env bash
cd /home/ubuntu/ai-employee
source $HOME/.local/bin/env
VAULT_PATH=./vault HEALTH_PORT=8080 uv run python cloud/health_monitor.py
EOF
chmod +x ~/ai-employee/cloud/start_health.sh
```

> **CRITICAL:** PM2 + uv gotcha: Do NOT use `interpreter` and `interpreter_args` in PM2
> ecosystem config with `uv`. It causes `SyntaxError: unterminated string literal` because
> PM2 tries to run the Python file through Node.js. Always use shell wrapper scripts.

### Step 4.2: Create PM2 ecosystem config

```bash
cat > ~/ai-employee/cloud/ecosystem.config.js << 'JSEOF'
module.exports = {
  apps: [
    {
      name: "ai-employee-cloud",
      script: "/home/ubuntu/ai-employee/cloud/start_cloud.sh",
      cwd: "/home/ubuntu/ai-employee",
      max_restarts: 10,
      min_uptime: "30s",
      restart_delay: 5000,
      log_file: "/home/ubuntu/ai-employee/logs/cloud-agent.log",
      error_file: "/home/ubuntu/ai-employee/logs/cloud-agent-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      watch: false,
    },
    {
      name: "health-monitor",
      script: "/home/ubuntu/ai-employee/cloud/start_health.sh",
      cwd: "/home/ubuntu/ai-employee",
      max_restarts: 5,
      log_file: "/home/ubuntu/ai-employee/logs/health.log",
      error_file: "/home/ubuntu/ai-employee/logs/health-error.log",
      watch: false,
    },
  ],
};
JSEOF
```

### Step 4.3: Create logs directory and start PM2

```bash
mkdir -p ~/ai-employee/logs
cd ~/ai-employee
pm2 start cloud/ecosystem.config.js
```

> **VERIFY:** Run `pm2 status` — both processes should show `online` status.
> If any show `errored`, check logs: `pm2 logs <process-name> --lines 20 --nostream`

### Step 4.4: Test health endpoint

```bash
curl http://localhost:8080/health
```

> **VERIFY:** Should return JSON with `"status": "healthy"` and both PM2 processes showing `"online"`.

### Step 4.5: Check cloud agent logs

```bash
pm2 logs ai-employee-cloud --lines 15 --nostream
```

> **VERIFY:** Should show:
> - `Starting AI Employee CLOUD Agent`
> - `Starting orchestrator`
> - Watcher start messages (Gmail, Facebook, LinkedIn, Twitter)
> - WhatsApp should be SKIPPED (cloud zone)
> - If items exist in Needs_Action, you should see `[cloud] Claimed:` and `[cloud] Drafted and moved to Pending_Approval:` messages

### Step 4.6: Enable auto-start on boot

```bash
pm2 save
pm2 startup
```

> The `pm2 startup` command outputs a `sudo env PATH=...` command.
> **You MUST copy and run that exact command.** Then run `pm2 save` again.

```bash
sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u ubuntu --hp /home/ubuntu
pm2 save
```

---

## PHASE 5: Odoo on Cloud via Docker (Run via SSH on the VM)

### Step 5.1: Create Odoo Docker directory

```bash
mkdir -p ~/ai-employee/cloud/odoo
```

### Step 5.2: Create docker-compose.yml

```bash
cat > ~/ai-employee/cloud/odoo/docker-compose.yml << 'YAMLEOF'
version: '3.8'

services:
  odoo-db:
    image: postgres:16
    container_name: odoo-db
    environment:
      POSTGRES_DB: odoo
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo_secure_pass_change_me
    volumes:
      - odoo-db-data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo"]
      interval: 10s
      timeout: 5s
      retries: 5

  odoo:
    image: odoo:17.0
    container_name: odoo-app
    depends_on:
      odoo-db:
        condition: service_healthy
    ports:
      - "8069:8069"
    environment:
      HOST: odoo-db
      PORT: 5432
      USER: odoo
      PASSWORD: odoo_secure_pass_change_me
    volumes:
      - odoo-data:/var/lib/odoo
      - odoo-addons:/mnt/extra-addons
    restart: unless-stopped

volumes:
  odoo-db-data:
  odoo-data:
  odoo-addons:
YAMLEOF
```

> **NOTE:** Using `odoo:17.0` because Odoo 19 may not have an official Docker image yet.
> If `odoo:19` is available, use that instead. Check with: `sudo docker pull odoo:19`

### Step 5.3: Start Odoo

```bash
cd ~/ai-employee/cloud/odoo
sudo docker compose up -d
```

> **VERIFY:** Run `sudo docker compose ps` — both containers should show `running` or `Up`.
> Odoo web UI will be at `http://<VM_IP>:8069` (requires firewall port open — see Phase 7).

### Step 5.4: Create Odoo backup script

```bash
cat > ~/ai-employee/cloud/odoo/backup_odoo.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="$HOME/ai-employee/backups/odoo"
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d_%H%M%S)
sudo docker exec odoo-db pg_dump -U odoo odoo | gzip > "$BACKUP_DIR/odoo_${DATE}.sql.gz"
ls -t "$BACKUP_DIR"/odoo_*.sql.gz | tail -n +8 | xargs -r rm
echo "[$(date -u)] Odoo backup complete: odoo_${DATE}.sql.gz"
EOF
chmod +x ~/ai-employee/cloud/odoo/backup_odoo.sh
```

### Step 5.5: Schedule daily backup (cron)

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * /home/ubuntu/ai-employee/cloud/odoo/backup_odoo.sh >> /home/ubuntu/ai-employee/logs/odoo_backup.log 2>&1") | crontab -
```

> **VERIFY:** Run `crontab -l` to confirm the entry was added.

---

## PHASE 6: Vault Git Sync (Run via SSH on the VM + Local)

### Step 6.1: Create a private GitHub repo for the vault

On GitHub, create a new **private** repository named `ai-employee-vault`.
Do NOT add README or .gitignore.

### Step 6.2: Initialize vault as a git repo on the VM

```bash
cd ~/ai-employee/vault
git init
git config user.name "AI-Employee-Cloud"
git config user.email "cloud-agent@ai-employee.local"
```

### Step 6.3: Create vault .gitignore

```bash
cat > ~/ai-employee/vault/.gitignore << 'EOF'
.obsidian/workspace.json
Logs/debug_screenshot_*.png
In_Progress/local/
EOF
```

### Step 6.4: Push vault to GitHub

```bash
cd ~/ai-employee/vault
git add -A
git commit -m "Initial vault sync from cloud"
git branch -M main
git remote add origin https://github.com/<GITHUB_USERNAME>/ai-employee-vault.git
git push -u origin main
```

> Use GitHub Personal Access Token as password when prompted.

### Step 6.5: Configure git credential caching

```bash
cd ~/ai-employee/vault
git config credential.helper store
```

> Next `git push` will save credentials permanently.

### Step 6.6: Create Cloud vault sync script

```bash
cat > ~/ai-employee/cloud/vault_sync.sh << 'BASHEOF'
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
BASHEOF
chmod +x ~/ai-employee/cloud/vault_sync.sh
```

### Step 6.7: Schedule vault sync (every 2 minutes)

```bash
(crontab -l 2>/dev/null; echo "*/2 * * * * /home/ubuntu/ai-employee/cloud/vault_sync.sh >> /home/ubuntu/ai-employee/logs/cron_sync.log 2>&1") | crontab -
```

> **VERIFY:** Run `crontab -l` to confirm both cron entries exist (backup + sync).

### Step 6.8: Set up vault sync on LOCAL machine (Windows)

Create this file on the user's local machine at `<LOCAL_PROJECT_PATH>/cloud/vault_sync_local.ps1`:

```powershell
# vault_sync_local.ps1 — Run on LOCAL machine
$ErrorActionPreference = "Stop"
$VaultDir = ".\vault"

Push-Location $VaultDir
try {
    git pull origin main --no-edit
    $status = git status --porcelain
    if ($status) {
        git add -A
        git commit -m "local-sync: $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')"
        git push origin main
        Write-Host "Pushed local changes"
    } else {
        Write-Host "No local changes to push"
    }
} finally {
    Pop-Location
}
```

---

## PHASE 7: Updated main.py with Zone Support (Run via SSH on the VM)

**CRITICAL:** The existing `main.py` must be updated so that when run locally with
`--zone local`, it uses the `LocalOrchestrator` (which merges Cloud signals into Dashboard).
Without this, the Local side of Platinum doesn't work.

### Step 12.1: Read current main.py

```bash
cat ~/ai-employee/main.py
```

### Step 12.2: Replace main.py with zone-aware version

```bash
cat > ~/ai-employee/main.py << 'PYEOF'
"""AI Employee — entry point.

Supports both Cloud and Local zones via AGENT_ZONE env var.
Default: local (safe — full execution capabilities).

Usage:
    uv run python main.py                  # Local mode (default)
    uv run python main.py --zone cloud     # Cloud mode
    uv run python main.py --zone local     # Explicit local mode
    uv run python main.py --dry-run        # Dry run mode
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv("config/.env")

from backend.orchestrator.orchestrator import OrchestratorConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Employee")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--zone",
        choices=["cloud", "local"],
        default=None,
        help="Override AGENT_ZONE (default: from env or 'local')",
    )
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
    if args.zone:
        os.environ["AGENT_ZONE"] = args.zone

    zone = os.getenv("AGENT_ZONE", "local").lower()
    config = OrchestratorConfig.from_env()

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    if zone == "cloud":
        from backend.cloud.cloud_orchestrator import CloudOrchestrator

        logger.info("Starting AI Employee — CLOUD zone")
        orchestrator = CloudOrchestrator(config)
    else:
        from backend.cloud.cloud_orchestrator import LocalOrchestrator

        logger.info("Starting AI Employee — LOCAL zone")
        orchestrator = LocalOrchestrator(config)

    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("AI Employee stopped")


if __name__ == "__main__":
    main()
PYEOF
```

> **VERIFY:** `cd ~/ai-employee && uv run python main.py --help`
> Should show `--zone` and `--dry-run` options.

### Step 12.3: Also update main.py on LOCAL machine

The same `main.py` must exist on the user's local machine. Either:
- Push from VM to GitHub and pull locally, OR
- Create the same file locally

On the LOCAL machine, replace the existing `main.py` with the exact same content above.

---

## PHASE 8: HTTPS for Odoo via Caddy (Run via SSH on the VM)

The hackathon requires Odoo with HTTPS. Caddy is the simplest reverse proxy for auto-HTTPS.

### Step 13.1: Install Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

### Step 13.2: Configure Caddy for IP-based HTTPS (self-signed)

Since we likely don't have a domain, use self-signed TLS:

```bash
sudo tee /etc/caddy/Caddyfile << 'EOF'
:443 {
    tls internal
    reverse_proxy localhost:8069
}

:8443 {
    tls internal
    reverse_proxy localhost:8080
}
EOF
```

### Step 13.3: Restart Caddy

```bash
sudo systemctl restart caddy
sudo systemctl enable caddy
```

> **VERIFY:** `sudo systemctl status caddy` should show `active (running)`.
> Access Odoo at `https://<VM_IP>:443` (browser will warn about self-signed cert — that's OK).

> **NOTE:** If the user has a domain name, replace `:443` with `yourdomain.com` and Caddy
> will automatically provision a real Let's Encrypt certificate.

---

## PHASE 9: Platinum Demo Test Script (Run via SSH on the VM)

The hackathon requires this specific demo scenario to pass:
> Email arrives while Local is offline → Cloud drafts reply + writes approval file →
> when Local returns, user approves → Local executes send via MCP → logs → moves task to /Done.

### Step 9.1: Create the demo test script

```bash
cat > ~/ai-employee/cloud/platinum_demo_test.sh << 'BASHEOF'
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
BASHEOF
chmod +x ~/ai-employee/cloud/platinum_demo_test.sh
```

### Step 9.2: Run the demo test

```bash
cd ~/ai-employee
bash cloud/platinum_demo_test.sh
```

> **VERIFY:** All checks should show ✅ PASS.

---

## PHASE 10: Update README.md for Platinum (Run via SSH on the VM)

### Step 10.1: Update tier declaration in README

Find the tier declaration section in README.md and update it. At minimum, add this section:

```bash
cat >> ~/ai-employee/README.md << 'MDEOF'

---

## Tier Declaration: Platinum ✅

| Requirement | Status |
|-------------|--------|
| All Gold requirements | ✅ Implemented |
| Cloud VM running 24/7 (Oracle Cloud) | ✅ PM2 + health monitoring |
| Work-Zone Specialization (Cloud/Local) | ✅ agent_role.py |
| Delegation via Synced Vault (Git) | ✅ vault_sync.sh + cron |
| Security: secrets never sync | ✅ .gitignore enforced |
| Odoo on Cloud with HTTPS + backups | ✅ Docker + Caddy + cron |
| Platinum demo scenario passing | ✅ Validated |

### Cloud Architecture

```
CLOUD VM (24/7)                    LOCAL (Your PC)
├── Gmail Watcher               ├── Approvals (Obsidian)
├── Facebook/LinkedIn/Twitter   ├── WhatsApp Watcher
├── Email triage + drafts       ├── Payment execution
├── Social post drafts          ├── Final send/post
├── CEO Briefing generation     ├── Dashboard.md (writer)
├── Odoo (draft-only)           └── All secrets
└── vault/ ◄── Git sync ──► vault/
```
MDEOF
```

---

## PHASE 11: Create Project Skill File (Run via SSH on the VM)

The hackathon requires: "All AI functionality should be implemented as Agent Skills."

### Step 11.1: Create the platinum-cloud skill

```bash
mkdir -p ~/ai-employee/skills/platinum-cloud
cat > ~/ai-employee/skills/platinum-cloud/SKILL.md << 'MDEOF'
---
name: platinum-cloud
description: >
  Cloud deployment and multi-agent coordination for the Personal AI Employee.
  Manages Work-Zone Specialization between Cloud and Local agents,
  vault synchronization via Git, claim-by-move coordination,
  and the Cloud→Local approval workflow.
trigger: Cloud deployment, multi-agent, vault sync, work-zone
tier: platinum
---

# Platinum Cloud Skill

## Purpose
Coordinate the Cloud↔Local split of the AI Employee system.

## Components
- `backend/cloud/agent_role.py` — Zone capabilities and ClaimManager
- `backend/cloud/cloud_orchestrator.py` — CloudOrchestrator and LocalOrchestrator
- `cloud/cloud_main.py` — Cloud VM entry point
- `cloud/health_monitor.py` — /health HTTP endpoint
- `cloud/vault_sync.sh` — Git-based vault synchronization

## Work-Zone Rules
- **Cloud**: watches Gmail/Facebook/LinkedIn/Twitter, creates drafts, generates briefings
- **Local**: watches WhatsApp, executes approvals, sends emails/posts, writes Dashboard
- **Claim-by-move**: first agent to move file to In_Progress/<agent>/ owns it
- **Single-writer**: only Local writes Dashboard.md; Cloud writes to Updates/
- **Secrets**: never leave Local (.env, tokens, sessions)

## Vault Sync Flow
1. Cloud creates drafts → pushes to GitHub
2. Local pulls → user reviews in Obsidian
3. Local approves → pushes to GitHub
4. Cloud pulls → sees approval (or Local executes directly)

## Demo Flow (Platinum Gate)
1. Email arrives while Local offline
2. Cloud Gmail Watcher detects → creates Needs_Action file
3. Cloud claims → drafts reply → moves to Pending_Approval
4. Cloud writes signal to Updates/
5. Vault syncs to GitHub
6. Local pulls → user reviews → moves to Approved/
7. Local agent executes send via MCP
8. File moves to Done/, logged
MDEOF
```

---

## PHASE 12: Firewall Configuration (Run via SSH on the VM)

### Step 12.1: Open required ports

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8069 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save
```

> If `netfilter-persistent` is not installed:
> ```bash
> sudo apt-get install -y iptables-persistent
> sudo netfilter-persistent save
> ```

### Step 12.2: Also open ports in Oracle Cloud Security List

This must be done in the Oracle Cloud Console (browser), NOT via SSH:

1. Go to **Networking → Virtual Cloud Networks → your VCN**
2. Click **Security** tab → **Security Lists** → **Default Security List**
3. Click **Add Ingress Rules**
4. Add these rules:
   - **Port 8069** (Odoo): Source CIDR `0.0.0.0/0`, TCP, Destination Port `8069`
   - **Port 8080** (Health): Source CIDR `0.0.0.0/0`, TCP, Destination Port `8080`

> **SECURITY NOTE:** For production, restrict Source CIDR to your IP only.

---

## PHASE 13: SSH Hardening (Run via SSH on the VM)

### Step 13.1: Disable password authentication

```bash
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### Step 13.2: Install fail2ban

```bash
sudo apt-get install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Step 13.3: Enable automatic security updates

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

> Select "Yes" when prompted.

---

## PHASE 14: Validation Checklist

Run these checks to confirm everything is working:

### Check 1: PM2 processes
```bash
pm2 status
```
> **EXPECT:** Both `ai-employee-cloud` and `health-monitor` showing `online`.

### Check 2: Health endpoint
```bash
curl http://localhost:8080/health
```
> **EXPECT:** JSON with `"status": "healthy"` and both processes `"online"`.

### Check 3: Cloud agent logs
```bash
pm2 logs ai-employee-cloud --lines 10 --nostream
```
> **EXPECT:** No crash errors. Should show orchestrator running, watchers started.

### Check 4: Gmail watcher working
```bash
ls -la ~/ai-employee/vault/Needs_Action/
ls -la ~/ai-employee/vault/Pending_Approval/
```
> **EXPECT:** Email files being created in Needs_Action and moved to Pending_Approval.

### Check 5: Odoo running (if deployed)
```bash
sudo docker compose -f ~/ai-employee/cloud/odoo/docker-compose.yml ps
```
> **EXPECT:** Both `odoo-db` and `odoo-app` showing `Up` or `running`.

### Check 6: Cron jobs
```bash
crontab -l
```
> **EXPECT:** Two entries — vault sync (every 2 min) and Odoo backup (daily at 3 AM).

### Check 7: Auto-start on reboot
```bash
sudo systemctl status pm2-ubuntu
```
> **EXPECT:** `active (running)` status.

### Check 8: External health check
From your LOCAL machine browser, visit: `http://<VM_IP>:8080/health`
> **EXPECT:** JSON health response (requires firewall port 8080 open).

---

## Troubleshooting

### PM2 process keeps restarting
```bash
pm2 logs <process-name> --lines 30 --nostream
```
Look for the actual Python error. Common issues:
- Missing dependencies: Run `uv sync` again
- Missing config files: Check `ls config/`
- Import errors: Check Python path with `uv run python -c "import backend; print('OK')"`

### SSH connection drops
Use keep-alive: `ssh -o ServerAliveInterval=60 -i <key> ubuntu@<ip>`

### Playwright/Chromium crashes
Missing shared libraries. Run:
```bash
uv run playwright install-deps chromium
```

### Watcher fails with "session not found"
Session folders (WhatsApp, LinkedIn, etc.) are local-only and NOT on the Cloud VM.
Cloud watchers for LinkedIn/Twitter/Facebook will fail on first run because they need
browser sessions. To fix: run `--setup` once in headed mode (requires X11 forwarding or VNC).
Alternatively, accept that these watchers will fail gracefully on Cloud and only Gmail works.

### Docker permission denied
```bash
sudo docker compose ...  # prefix with sudo
# OR re-login to pick up docker group:
exit
ssh -i <key> ubuntu@<ip>
```

---

## PM2 Quick Reference

```bash
pm2 status                          # View all processes
pm2 logs <name> --lines 20         # View logs
pm2 restart <name>                  # Restart a process
pm2 restart all                     # Restart all
pm2 stop all                        # Stop all
pm2 delete all                      # Remove all
pm2 save                            # Save process list
pm2 startup                         # Generate auto-start script
```

---

## Files Created by This Skill

```
~/ai-employee/
├── main.py                            # UPDATED: --zone flag for Cloud/Local
├── backend/cloud/
│   ├── __init__.py
│   ├── agent_role.py                  # Work-Zone capabilities + ClaimManager
│   └── cloud_orchestrator.py          # CloudOrchestrator + LocalOrchestrator
├── cloud/
│   ├── cloud_main.py                  # Cloud VM entry point
│   ├── health_monitor.py              # /health HTTP endpoint
│   ├── start_cloud.sh                 # PM2 wrapper for cloud agent
│   ├── start_health.sh                # PM2 wrapper for health monitor
│   ├── ecosystem.config.js            # PM2 process config
│   ├── vault_sync.sh                  # Git-based vault sync (cron)
│   ├── vault_sync_local.ps1           # Windows sync script for Local
│   ├── platinum_demo_test.sh          # Demo validation script
│   └── odoo/
│       ├── docker-compose.yml         # Odoo + PostgreSQL
│       └── backup_odoo.sh             # Daily DB backup
├── skills/
│   └── platinum-cloud/
│       └── SKILL.md                   # Platinum skill documentation
├── vault/
│   ├── In_Progress/cloud/             # Files claimed by Cloud
│   ├── In_Progress/local/             # Files claimed by Local
│   └── Updates/                       # Cloud→Local signals
├── logs/                              # PM2 and cron logs
└── README.md                          # UPDATED: Platinum tier declaration
```
