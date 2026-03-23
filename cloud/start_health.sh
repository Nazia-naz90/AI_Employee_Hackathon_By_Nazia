#!/usr/bin/env bash
cd /home/ubuntu/ai-employee
source $HOME/.local/bin/env
VAULT_PATH=./vault HEALTH_PORT=8080 uv run python cloud/health_monitor.py
