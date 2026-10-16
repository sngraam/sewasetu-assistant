"""
mcp/shared.py — Backward-compatibility shim.

All logic has moved to:
  config.py           — constants
  db/pool.py          — connection pool
  db/citizen.py       — citizen queries
  db/officer.py       — officer queries
  domain/time.py      — time helpers
  domain/validation.py — validate_application, parse_dob, age_on
  domain/application.py — create_application, withdraw_application, build_dossier
  domain/audit.py     — write_audit
  middleware/masking.py — mask_account, mask_mobile
  middleware/otp.py   — send_otp, verify_otp

This file re-exports everything so existing callers (e.g. tests) still work
without changes while the codebase migrates.
"""
# ruff: noqa: F401
from config import (
    BLOCKS, ACTIVE_STATUSES, MIN_AGE, SLA_DAYS, SCHEME_DEADLINE,
    AGENT_BLOCKS, DECLARED_PREFIX, VALID_AGE_PROOFS, IST,
    ADMIN_USERNAME, ADMIN_PASSWORD,
)
from db.pool import db_conn as get_db_connection_ctx, health_check
from db.citizen import (
    get_apps_by_mobile,
    get_app_by_no,
    has_active_application,
    get_decision_note,
)
from db.officer import (
    list_applications as list_applications_db,
    get_audit_trail,
    find_possible_duplicates,
    dashboard_stats as dashboard_stats_db,
    decide_application as decide_application_db,
)
from domain.time import now_ist, now_str
from domain.validation import validate_application, parse_dob, age_on
from domain.application import (
    create_application,
    withdraw_application as withdraw_application_db,
    build_dossier as get_dossier,
)
from domain.audit import write_audit
from middleware.masking import mask_account, mask_mobile
from middleware.otp import send_otp, verify_otp

import hashlib as _hashlib


def hash_password(p: str) -> str:
    return _hashlib.sha256(p.encode("utf-8")).hexdigest()


def auth_citizen(mobile: str):
    """Dev-mode helper — JWT proves identity in production."""
    from db.citizen import get_apps_by_mobile as _gam
    apps = _gam(mobile)
    if apps:
        return {"mobile": mobile, "name": apps[0].get("applicant_name", "")}
    return None


def auth_officer(username: str, password: str) -> bool:
    """Dev-mode helper — JWT proves identity in production."""
    if not ADMIN_PASSWORD:
        return False
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def get_db_connection():
    """Legacy: return a raw connection. Prefer db.pool.db_conn() context manager."""
    from db.pool import get_conn
    return get_conn()
