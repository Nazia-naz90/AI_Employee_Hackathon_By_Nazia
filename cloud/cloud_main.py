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
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / "config" / ".env")

os.environ["AGENT_ZONE"] = "cloud"

from backend.cloud.cloud_orchestrator import CloudOrchestrator
from backend.orchestrator.orchestrator import OrchestratorConfig


def setup_logging(log_level: str) -> None:
    """Configure logging format and level."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Employee — Cloud Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without executing them",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"

    setup_logging(args.log_level)

    config = OrchestratorConfig.from_env()

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Starting AI Employee CLOUD Agent")
    logger.info("=" * 60)
    logger.info("DEV_MODE=%s, DRY_RUN=%s, ZONE=cloud", config.dev_mode, config.dry_run)
    logger.info("Vault path: %s", config.vault_path)
    logger.info("=" * 60)

    orchestrator = CloudOrchestrator(config)
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("Cloud agent stopped by user")
    except Exception as e:
        logger.exception("Cloud agent crashed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
