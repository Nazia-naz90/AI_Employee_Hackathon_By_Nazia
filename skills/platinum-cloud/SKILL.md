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

## Architecture

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

## Components

### Backend Module
- `backend/cloud/agent_role.py` — Zone capabilities and ClaimManager
- `backend/cloud/cloud_orchestrator.py` — CloudOrchestrator and LocalOrchestrator
- `cloud/cloud_main.py` — Cloud VM entry point
- `cloud/health_monitor.py` — /health HTTP endpoint

### Operations
- `cloud/vault_sync.sh` — Git-based vault synchronization (cron every 2 min)
- `cloud/vault_sync_local.ps1` — Windows sync script for Local
- `cloud/ecosystem.config.js` — PM2 process configuration
- `cloud/start_cloud.sh` — PM2 wrapper for cloud agent
- `cloud/start_health.sh` — PM2 wrapper for health monitor

### Odoo
- `cloud/odoo/docker-compose.yml` — Odoo + PostgreSQL containers
- `cloud/odoo/backup_odoo.sh` — Daily DB backup script

## Work-Zone Rules

| Capability | Cloud | Local |
|------------|-------|-------|
| Gmail Watcher | ✅ | ❌ |
| WhatsApp Watcher | ❌ | ✅ |
| Facebook Watcher | ✅ | ❌ |
| LinkedIn Watcher | ✅ | ❌ |
| Twitter Watcher | ✅ | ❌ |
| Email triage | ✅ | ✅ |
| Draft replies | ✅ | ✅ |
| Send email | ❌ | ✅ |
| Social post draft | ✅ | ❌ |
| Post social | ❌ | ✅ |
| Payment execution | ❌ | ✅ |
| Write Dashboard | ❌ | ✅ |
| Odoo read | ✅ | ✅ |
| Odoo draft | ✅ | ✅ |
| Odoo post | ❌ | ✅ |

### Claim-by-Move Protocol

1. First agent to move file from `Needs_Action/` to `In_Progress/<agent>/` owns it
2. Other agents must ignore files already in `In_Progress/`
3. After processing, Cloud moves to `Pending_Approval/` for human review
4. Local executes approved items and moves to `Done/`

### Single-Writer Dashboard

- Only Local writes to `Dashboard.md`
- Cloud writes signals to `Updates/` directory
- Local merges signals from `Updates/` into Dashboard periodically

## Secrets Policy

**NEVER sync these to Cloud:**
- `.env` file (except AGENT_ZONE=cloud on Cloud)
- `credentials.json` (Gmail OAuth)
- `token.json` (Gmail token)
- `whatsapp_session/`
- `meta_session/` (Facebook/Instagram)
- `twitter_session/`
- `linkedin_session/`

All secrets stay on Local machine only.

## Vault Sync Flow

1. Cloud creates drafts → pushes to GitHub vault repo
2. Local pulls → user reviews in Obsidian
3. Local approves (moves to `Approved/`) → pushes to GitHub
4. Local agent executes send → moves to `Done/`

## Demo Flow (Platinum Gate)

**Scenario:** Email arrives while Local is offline

1. Email arrives in Gmail
2. Cloud Gmail Watcher detects → creates `Needs_Action/email-*.md`
3. Cloud claims file → moves to `In_Progress/cloud/`
4. Cloud drafts reply → moves to `Pending_Approval/`
5. Cloud writes signal to `Updates/signal_*.md`
6. Vault syncs to GitHub
7. Local comes online → pulls vault changes
8. User reviews in Obsidian → moves to `Approved/`
9. Local agent executes send via MCP
10. File moves to `Done/`, logged

## Commands

### Cloud VM

```bash
# View PM2 status
pm2 status

# View logs
pm2 logs ai-employee-cloud --lines 20

# Restart cloud agent
pm2 restart ai-employee-cloud

# Test health endpoint
curl http://localhost:8080/health

# Run demo validation
bash cloud/platinum_demo_test.sh

# Manual vault sync
bash cloud/vault_sync.sh
```

### Local (Windows)

```powershell
# Sync vault
.\cloud\vault_sync_local.ps1

# Run local agent
uv run python main.py --zone local

# Check vault status
git -C vault status
```

## Troubleshooting

### PM2 process keeps restarting
```bash
pm2 logs ai-employee-cloud --lines 30 --nostream
```

Common issues:
- Missing dependencies: Run `uv sync` again
- Missing config files: Check `ls config/`
- Import errors: Check Python path

### Watcher fails with "session not found"
Session folders are local-only and NOT on the Cloud VM.
Cloud watchers for LinkedIn/Twitter/Facebook need browser sessions.
Run `--setup` once in headed mode if needed.

### Vault sync fails
```bash
cd ~/ai-employee/vault
git status
git pull origin main
```

### Health endpoint not responding
```bash
# Check if health monitor is running
pm2 status health-monitor

# View logs
pm2 logs health-monitor --lines 20
```

## Files Created

```
~/ai-employee/
├── backend/cloud/
│   ├── __init__.py
│   ├── agent_role.py
│   └── cloud_orchestrator.py
├── cloud/
│   ├── cloud_main.py
│   ├── health_monitor.py
│   ├── start_cloud.sh
│   ├── start_health.sh
│   ├── ecosystem.config.js
│   ├── vault_sync.sh
│   ├── vault_sync_local.ps1 (also on Local)
│   ├── platinum_demo_test.sh
│   └── odoo/
│       ├── docker-compose.yml
│       └── backup_odoo.sh
├── skills/platinum-cloud/
│   └── SKILL.md (this file)
├── vault/
│   ├── In_Progress/cloud/
│   ├── In_Progress/local/
│   └── Updates/
└── logs/
```
