"""
mcp/config.py — Central configuration for the Sewa Setu MCP servers.

ALL environment reads happen here. Every other module imports from config.
This makes it trivial to test with different values and impossible to
accidentally hard-code a default buried deep in shared code.

Env vars are documented in mcp/.env.example.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ── Timezone ──────────────────────────────────────────────────────────────────
IST = ZoneInfo("Asia/Kolkata")

# ── Database ──────────────────────────────────────────────────────────────────
DB_HOST     : str = os.environ.get("DB_HOST",     "db")
DB_PORT     : str = os.environ.get("DB_PORT",     "5432")
DB_NAME     : str = os.environ.get("DB_NAME",     "sewasetu")
DB_USER     : str = os.environ.get("DB_USER",     "sewasetu")
DB_PASSWORD : str = os.environ.get("DB_PASSWORD", "sewasetu123")

DB_POOL_MIN : int = int(os.environ.get("DB_POOL_MIN", "2"))
DB_POOL_MAX : int = int(os.environ.get("DB_POOL_MAX", "10"))

# ── SMS gateway ───────────────────────────────────────────────────────────────
SMS_GATEWAY_URL      : str = os.environ.get("SMS_GATEWAY_URL",      "http://smsgw:8025")
OTP_VALIDITY_SECONDS : int = int(os.environ.get("OTP_VALIDITY_SECONDS", "300"))
OTP_MAX_PER_WINDOW   : int = int(os.environ.get("OTP_MAX_PER_WINDOW",   "3"))
OTP_WINDOW_SECONDS   : int = int(os.environ.get("OTP_WINDOW_SECONDS",   "600"))   # 10 min

# ── Portal admin (dev bypass only — never used in prod JWT flow) ──────────────
ADMIN_USERNAME : str = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD : str = os.environ.get("ADMIN_PASSWORD", "")

# ── JWT / OAuth audience ──────────────────────────────────────────────────────
PORTAL_ISSUER   : str = os.environ.get("PORTAL_ISSUER",   "").rstrip("/")
PORTAL_JWKS_URL : str = os.environ.get("PORTAL_JWKS_URL", "") or (PORTAL_ISSUER + "/.well-known/jwks.json")
CITIZEN_MCP_URL : str = os.environ.get("CITIZEN_MCP_URL", "http://localhost:8001/mcp").rstrip("/")
OFFICER_MCP_URL : str = os.environ.get("OFFICER_MCP_URL", "http://localhost:8002/mcp").rstrip("/")

DEV_INSECURE_MOBILE  : str = os.environ.get("DEV_INSECURE_MOBILE",  "").strip()
DEV_INSECURE_OFFICER : str = os.environ.get("DEV_INSECURE_OFFICER", "").strip()

# ── Scheme rules ──────────────────────────────────────────────────────────────
MIN_AGE  : int = int(os.environ.get("MIN_AGE",  "60"))
SLA_DAYS : int = int(os.environ.get("SLA_DAYS", "15"))

SCHEME_DEADLINE : datetime = datetime.strptime(
    os.environ.get("SCHEME_DEADLINE", "2026-10-31 23:59"), "%Y-%m-%d %H:%M"
)

BLOCKS : list[str] = [
    "Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"
]

AGENT_BLOCKS : list[str] = [
    b.strip()
    for b in os.environ.get("AGENT_BLOCKS", "Sonari,Rajapara,Dhemaji Pathar").split(",")
    if b.strip()
]

ACTIVE_STATUSES : tuple[str, ...] = ("PENDING", "APPROVED", "DEEMED_APPROVED")

# ── Age proof — declared (not uploaded) marker ────────────────────────────────
DECLARED_PREFIX : str = "declared://"

VALID_AGE_PROOFS : tuple[str, ...] = (
    "Voter ID",
    "Birth certificate",
    "School leaving certificate",
)

# ── Server ports ──────────────────────────────────────────────────────────────
CITIZEN_MCP_HOST : str = os.environ.get("FASTMCP_HOST", "0.0.0.0")
CITIZEN_MCP_PORT : int = int(os.environ.get("FASTMCP_PORT", "8001"))
OFFICER_MCP_HOST : str = os.environ.get("FASTMCP_HOST", "0.0.0.0")
OFFICER_MCP_PORT : int = int(os.environ.get("FASTMCP_PORT", "8002"))

# ── Service version (shown in /health) ───────────────────────────────────────
SERVICE_VERSION : str = os.environ.get("SERVICE_VERSION", "1.0.0")

# ── File upload ───────────────────────────────────────────────────────────────
# Shared volume with the Flask portal: /var/sewasetu/uploads
UPLOAD_ROOT  : str = os.environ.get("UPLOAD_ROOT",  "/var/sewasetu/uploads")
TEMP_ROOT    : str = os.environ.get("TEMP_ROOT",    "/var/sewasetu/uploads/.tmp")

# Accepted extensions and MIME types for age proof documents
ALLOWED_EXTENSIONS : tuple[str, ...] = (".pdf", ".jpg", ".jpeg", ".png")
MAX_FILE_SIZE_BYTES : int = int(os.environ.get("MAX_FILE_SIZE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
