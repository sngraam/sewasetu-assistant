"""
mcp/citizen_mcp.py — Citizen MCP entry point.

Wires the 7 citizen tools to the MCPServer and starts it on port 8001.
All logic lives in tools/citizen/*.py, prompts/, db/, and domain/.

Usage:
    python citizen_mcp.py

Dev bypass (no OAuth needed):
    DEV_INSECURE_MOBILE=9876543210 python citizen_mcp.py
"""
import sys
from pathlib import Path

# Make the mcp/ directory importable as a package root
sys.path.insert(0, str(Path(__file__).parent))

# ── Structured logging — must be first ───────────────────────────────────────
from middleware.logging_setup import configure as configure_logging
configure_logging("citizen_mcp")

import logging
log = logging.getLogger("sewasetu.citizen_mcp")

# ── MCP framework ─────────────────────────────────────────────────────────────
from mcp.server.mcpserver import MCPServer

# ── Internal modules ──────────────────────────────────────────────────────────
import config
from auth import server_kwargs
from db.pool import health_check
from prompts.citizen_instructions import build as build_instructions

# ── Tool modules (one import per tool file) ───────────────────────────────────
from tools.citizen import who_am_i, scheme_info, eligibility, apply, status, withdraw, upload

# ── Server ────────────────────────────────────────────────────────────────────
mcp = MCPServer(
    name="Sewa Setu — Citizen Assistant",
    instructions=build_instructions(),
    **server_kwargs("citizen"),
)

# ── Register all tools ────────────────────────────────────────────────────────
who_am_i.register(mcp)
scheme_info.register(mcp)
eligibility.register(mcp)
apply.register(mcp)
status.register(mcp)
withdraw.register(mcp)
upload.register(mcp)   # stage_document + check_staged_document


# ── Health resource (used by Docker healthcheck + monitoring) ─────────────────
@mcp.resource("health://status")
def health_status() -> str:
    """Service liveness check. Returns JSON with DB connectivity status."""
    import json
    db_ok = health_check()
    return json.dumps({
        "status":  "ok" if db_ok else "degraded",
        "db":      "ok" if db_ok else "error",
        "service": "citizen-mcp",
        "version": config.SERVICE_VERSION,
    })


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info(
        "Starting Citizen MCP",
        extra={
            "action":  "startup",
            "version": config.SERVICE_VERSION,
            "host":    config.CITIZEN_MCP_HOST,
            "port":    config.CITIZEN_MCP_PORT,
            "auth":    "dev-bypass" if config.DEV_INSECURE_MOBILE else "jwt",
        },
    )
    mcp.run(
        transport="streamable-http",
        host=config.CITIZEN_MCP_HOST,
        port=config.CITIZEN_MCP_PORT,
        streamable_http_path="/",   # Caddy proxies /mcp/citizen → / on this container
    )
