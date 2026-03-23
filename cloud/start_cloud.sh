#!/usr/bin/env bash
cd /home/ubuntu/ai-employee
source $HOME/.local/bin/env
AGENT_ZONE=cloud uv run python cloud/cloud_main.py
