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
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv("config/.env")

from backend.orchestrator.orchestrator import OrchestratorConfig


def setup_logging(log_level: str) -> None:
    """Configure logging format and level."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Employee")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without executing them",
    )
    parser.add_argument(
        "--zone",
        choices=["cloud", "local"],
        default=None,
        help="Override AGENT_ZONE (default: from env or 'local')",
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
    if args.zone:
        os.environ["AGENT_ZONE"] = args.zone

    zone = os.getenv("AGENT_ZONE", "local").lower()
    config = OrchestratorConfig.from_env()

    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)

    if zone == "cloud":
        from backend.cloud.cloud_orchestrator import CloudOrchestrator

        logger.info("=" * 60)
        logger.info("Starting AI Employee — CLOUD zone")
        logger.info("=" * 60)
        orchestrator = CloudOrchestrator(config)
    else:
        from backend.cloud.cloud_orchestrator import LocalOrchestrator

        logger.info("=" * 60)
        logger.info("Starting AI Employee — LOCAL zone")
        logger.info("=" * 60)
        orchestrator = LocalOrchestrator(config)

    logger.info("DEV_MODE=%s, DRY_RUN=%s, ZONE=%s", config.dev_mode, config.dry_run, zone)
    logger.info("Vault path: %s", config.vault_path)
    logger.info("=" * 60)

    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logger.info("AI Employee stopped by user")
    except Exception as e:
        logger.exception("AI Employee crashed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
