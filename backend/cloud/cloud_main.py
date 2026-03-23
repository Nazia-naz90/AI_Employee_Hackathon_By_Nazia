"""Cloud VM entry point for Personal AI Employee.

This is the main entry point for running the AI Employee on a cloud VM.
It configures the environment for cloud zone operation and runs CloudOrchestrator.

Usage:
    python -m backend.cloud.cloud_main

Environment:
    AGENT_ZONE=cloud (automatically set by this module)
    VAULT_PATH=./vault
    All other config from config/.env
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.cloud.cloud_orchestrator import CloudOrchestrator
from backend.orchestrator.orchestrator import OrchestratorConfig

logger = logging.getLogger(__name__)


def load_env_file(env_path: Path) -> None:
    """Load environment variables from .env file.

    Args:
        env_path: Path to the .env file
    """
    if not env_path.exists():
        logger.warning("Environment file not found: %s", env_path)
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] in ('"', "'"):
                    value = value[1:-1]
                # Only set if not already in environment
                if key and key not in os.environ:
                    os.environ[key] = value
                    logger.debug("Loaded env: %s=%s", key, "***" if "SECRET" in key or "KEY" in key or "TOKEN" in key else value)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for cloud orchestrator."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main() -> None:
    """Main entry point for cloud orchestrator."""
    # Set cloud zone
    os.environ["AGENT_ZONE"] = "cloud"
    logger.info("Agent zone set to: cloud")

    # Load environment from config/.env
    env_path = PROJECT_ROOT / "config" / ".env"
    logger.info("Loading environment from: %s", env_path)
    load_env_file(env_path)

    # Get log level from env (after loading .env)
    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(log_level)

    # Create orchestrator config from environment
    config = OrchestratorConfig.from_env()
    logger.info("Orchestrator config: VAULT_PATH=%s, DEV_MODE=%s, DRY_RUN=%s",
                config.vault_path, config.dev_mode, config.dry_run)

    # Create and run cloud orchestrator
    orchestrator = CloudOrchestrator(config)

    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception:
        logger.exception("Cloud orchestrator failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
