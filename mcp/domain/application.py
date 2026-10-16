"""
mcp/domain/application.py — Application lifecycle operations.

Orchestrates DB writes across multiple tables (applications, portal_users,
audit_log). Each function is a single unit of work — it either succeeds
completely or rolls back.
"""
from __future__ import annotations

import logging
import random

import config
from db.citizen import (
    insert_application,
    withdraw_application_row,
)
from domain.time import now_ist

log = logging.getLogger("sewasetu.domain.application")


def new_application_no() -> str:
    """Generate SSP{YY}{6-digit-random} — same format as portal."""
    return "SSP" + now_ist().strftime("%y") + str(random.randint(100000, 999999))


def create_application(mobile: str, cleaned: dict) -> tuple[int, str]:
    """
    Insert a validated application and create the status-portal account.

    Returns (application_id, application_no).
    Raises on DB error — caller should catch and present a user-friendly message.
    """
    app_no = new_application_no()
    submitted_at = now_ist()

    new_id = insert_application(mobile, app_no, cleaned, submitted_at)

    # Audit is written inside insert_application so the same transaction covers it.
    # Log for structured observability.
    log.info(
        "application_created application_no=%s mobile=%s block=%s declared=%s",
        app_no, mobile, cleaned.get("block"),
        str(cleaned.get("doc_path", "")).startswith(config.DECLARED_PREFIX),
    )
    return new_id, app_no


def withdraw_application(mobile: str, application_no: str) -> dict:
    """
    Withdraw a PENDING application.

    Returns {"success": True, ...} or {"error": "..."}.
    """
    result = withdraw_application_row(mobile, application_no, now_ist())
    if result.get("success"):
        log.info(
            "application_withdrawn application_no=%s mobile=%s",
            application_no, mobile,
        )
    return result


def build_dossier(application_no: str) -> dict | None:
    """
    Assemble the officer dossier for one application:
    full row + audit trail + computed flags.

    Returns None if the application doesn't exist.
    """
    from db.officer import (
        get_application_by_no,
        get_audit_trail,
        find_possible_duplicates,
    )
    from domain.validation import age_on, parse_dob
    from datetime import datetime

    app = get_application_by_no(application_no)
    if not app:
        return None

    # ── Flags ────────────────────────────────────────────────────────────────
    declared_only = str(app.get("doc_path") or "").startswith(config.DECLARED_PREFIX)

    # Parse DOB (comes back as ISO string from row_to_dict)
    dob_raw = app.get("dob")
    dob_date = None
    if dob_raw:
        try:
            dob_date = datetime.fromisoformat(str(dob_raw)).date()
        except ValueError:
            pass

    # Parse submitted_at
    sub_raw = app.get("submitted_at")
    submitted_date = now_ist().date()
    if sub_raw:
        try:
            submitted_date = datetime.fromisoformat(str(sub_raw)).date()
        except ValueError:
            pass

    age_ok = bool(dob_date and age_on(dob_date, submitted_date) >= config.MIN_AGE)

    days_pending = 0
    sla_overdue  = False
    if app.get("status") == "PENDING":
        days_pending = (now_ist().date() - submitted_date).days
        sla_overdue  = days_pending > config.SLA_DAYS

    # Duplicates — use the raw int id
    app_id = app.get("id") or 0
    duplicates = find_possible_duplicates(
        app_id,
        app.get("bank_account", ""),
        app.get("applicant_name", ""),
        dob_date,
    ) if app_id else []

    # Mask account in output — officer also sees full account for verification
    from middleware.masking import mask_account
    app["bank_account_masked"] = mask_account(app.get("bank_account", ""))

    app["audit_trail"] = get_audit_trail(app_id)

    age_proof_label = (
        str(app.get("doc_path", ""))
        .replace(config.DECLARED_PREFIX, "")
        .replace("_", " ")
        .title()
        if declared_only else "uploaded"
    )

    app["flags"] = {
        "age_ok":        age_ok,
        "declared_only": declared_only,
        "age_proof_note": (
            f"DECLARED ONLY — citizen stated they hold '{age_proof_label}' "
            "but no file was uploaded. Officer MUST verify the physical document before approving."
            if declared_only
            else "Document uploaded via web portal."
        ),
        "possible_duplicates": duplicates,
        "sla_overdue":  sla_overdue,
        "days_pending": days_pending,
    }

    return app
