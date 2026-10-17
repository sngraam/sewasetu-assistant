"""
mcp/officer_mcp.py — Officer MCP entry point.

Wires the 4 officer tools to the MCPServer and starts it on port 8002.
All logic lives in tools/officer/*.py, prompts/, db/, and domain/.

Usage:
    python officer_mcp.py

Dev bypass (no OAuth needed):
    DEV_INSECURE_OFFICER=admin python officer_mcp.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── Structured logging — must be first ───────────────────────────────────────
from middleware.logging_setup import configure as configure_logging
configure_logging("officer_mcp")

import logging
log = logging.getLogger("sewasetu.officer_mcp")

# ── MCP framework ─────────────────────────────────────────────────────────────
from mcp.server.mcpserver import MCPServer

# ── Internal modules ──────────────────────────────────────────────────────────
import config
from auth import server_kwargs
from db.pool import health_check
from prompts.officer_instructions import build as build_instructions

# ── Tool modules ──────────────────────────────────────────────────────────────
from tools.officer import queue, dossier, decide

# ── Server ────────────────────────────────────────────────────────────────────
mcp = MCPServer(
    name="Sewa Setu — Officer Dashboard",
    instructions=build_instructions(),
    **server_kwargs("officer"),
)

# ── Register all tools ────────────────────────────────────────────────────────
queue.register(mcp)
dossier.register(mcp)
decide.register(mcp)


# ── Health resource ───────────────────────────────────────────────────────────
@mcp.resource("health://status")
def health_status() -> str:
    """Service liveness check. Returns JSON with DB connectivity status."""
    import json
    db_ok = health_check()
    return json.dumps({
        "status":  "ok" if db_ok else "degraded",
        "db":      "ok" if db_ok else "error",
        "service": "officer-mcp",
        "version": config.SERVICE_VERSION,
    })


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info(
        "Starting Officer MCP",
        extra={
            "action":  "startup",
            "version": config.SERVICE_VERSION,
            "host":    config.OFFICER_MCP_HOST,
            "port":    config.OFFICER_MCP_PORT,
            "auth":    "dev-bypass" if config.DEV_INSECURE_OFFICER else "jwt",
        },
    )
    mcp.run(
        transport="streamable-http",
        host=config.OFFICER_MCP_HOST,
        port=config.OFFICER_MCP_PORT,
        streamable_http_path="/",   # Caddy proxies /mcp/officer → / on this container
    )
