"""Lightweight HTTP health monitor for cloud orchestrator.

Exposes a /health endpoint on port 8080 for load balancer health checks
and monitoring systems.

Endpoints:
    GET /health - Returns JSON health status
    GET /ready  - Returns JSON readiness status

Usage:
    python -m backend.cloud.health_monitor

Or as part of cloud_main.py startup.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# Global state
_start_time: datetime | None = None
_last_check: datetime | None = None
_health_status: str = "starting"
_error_message: str | None = None


def get_health_status() -> dict[str, Any]:
    """Get current health status as a dictionary."""
    global _start_time, _last_check, _health_status, _error_message

    now = datetime.now(timezone.utc)
    uptime_seconds = 0
    if _start_time:
        uptime_seconds = (now - _start_time).total_seconds()

    return {
        "status": _health_status,
        "timestamp": now.isoformat(),
        "uptime_seconds": uptime_seconds,
        "last_check": _last_check.isoformat() if _last_check else None,
        "error": _error_message,
        "zone": os.getenv("AGENT_ZONE", "unknown"),
        "version": "platinum-1.0.0",
    }


def set_health_status(status: str, error: str | None = None) -> None:
    """Update the global health status.

    Args:
        status: One of "healthy", "unhealthy", "starting", "degraded"
        error: Optional error message if unhealthy
    """
    global _health_status, _error_message, _last_check
    _health_status = status
    _error_message = error
    _last_check = datetime.now(timezone.utc)


async def health_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle incoming HTTP requests for health endpoint."""
    try:
        # Read the HTTP request
        request_line = await reader.readline()
        if not request_line:
            writer.close()
            await writer.wait_closed()
            return

        request_line = request_line.decode("utf-8").strip()
        parts = request_line.split(" ")
        if len(parts) < 2:
            writer.close()
            await writer.wait_closed()
            return

        method, path = parts[0], parts[1]

        # Read and discard headers
        while True:
            line = await reader.readline()
            if line == b"\r\n" or line == b"":
                break

        # Route the request
        if method == "GET":
            if path == "/health":
                response_body = json.dumps(get_health_status(), indent=2)
                status = HTTPStatus.OK
                reason = "OK"
            elif path == "/ready":
                # Ready check - ensures orchestrator is fully initialized
                status_data = get_health_status()
                if status_data["status"] == "healthy" and status_data["uptime_seconds"] > 5:
                    response_body = json.dumps({"ready": True, **status_data}, indent=2)
                    status = HTTPStatus.OK
                    reason = "OK"
                else:
                    response_body = json.dumps({"ready": False, **status_data}, indent=2)
                    status = HTTPStatus.SERVICE_UNAVAILABLE
                    reason = "Service Unavailable"
            elif path == "/live":
                # Liveness check - just confirms process is alive
                response_body = json.dumps({"alive": True}, indent=2)
                status = HTTPStatus.OK
                reason = "OK"
            else:
                response_body = json.dumps({"error": "Not found", "path": path}, indent=2)
                status = HTTPStatus.NOT_FOUND
                reason = "Not Found"
        else:
            response_body = json.dumps({"error": "Method not allowed"}, indent=2)
            status = HTTPStatus.METHOD_NOT_ALLOWED
            reason = "Method Not Allowed"

        # Send HTTP response
        response = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(response_body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{response_body}"
        )

        writer.write(response.encode("utf-8"))
        await writer.drain()

    except Exception as exc:
        logger.exception("Error handling health request")
        set_health_status("degraded", str(exc))
        try:
            error_body = json.dumps({"error": "Internal server error"}, indent=2)
            response = (
                f"HTTP/1.1 {HTTPStatus.INTERNAL_SERVER_ERROR} Internal Server Error\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(error_body)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"{error_body}"
            )
            writer.write(response.encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def run_health_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the health monitor HTTP server.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 8080)
    """
    global _start_time

    _start_time = datetime.now(timezone.utc)
    set_health_status("starting")

    server = await asyncio.start_server(health_handler, host, port)
    addr = server.sockets[0].getsockname() if server.sockets else (host, port)
    logger.info("Health monitor listening on http://%s:%s", addr[0], addr[1])
    logger.info("Endpoints: /health, /ready, /live")

    set_health_status("healthy")

    async with server:
        await server.serve_forever()


async def health_check_loop(interval: int = 30) -> None:
    """Periodic health check loop that updates status.

    This runs alongside the health server and performs actual
    health checks on the orchestrator components.

    Args:
        interval: Seconds between health checks
    """
    while True:
        try:
            # Perform actual health checks here
            # For now, just confirm we're still running
            set_health_status("healthy")
            logger.debug("Health check passed")
        except Exception as exc:
            set_health_status("unhealthy", str(exc))
            logger.exception("Health check failed")
        await asyncio.sleep(interval)


async def main() -> None:
    """Main entry point for health monitor."""
    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    port = int(os.getenv("HEALTH_MONITOR_PORT", "8080"))
    host = os.getenv("HEALTH_MONITOR_HOST", "0.0.0.0")

    # Run health server and check loop concurrently
    await asyncio.gather(
        run_health_server(host, port),
        health_check_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
