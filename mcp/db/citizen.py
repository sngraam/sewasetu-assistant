"""
mcp/db/citizen.py — All citizen-facing database queries.

No business logic here. Every function takes typed arguments, returns plain
dicts, and leaves transactions to the caller. Import from domain/ for logic.
"""
from __future__ import annotations

import hashlib
import logging

import psycopg2.extras

import config
from db.pool import db_conn, execute_query, get_conn, release_conn, row_to_dict

log = logging.getLogger("sewasetu.db.citizen")

_APP_COLS = (
    "id, application_no, applicant_name, mobile, dob, gender, marital_status, "
    "husband_name, village, block, bank_account, ifsc, doc_path, "
    "status, submitted_at, decided_at, decided_by"
)


# ── Read queries ──────────────────────────────────────────────────────────────

def get_apps_by_mobile(mobile: str) -> list[dict]:
    """All applications for a mobile, newest first."""
    return execute_query(
        f"SELECT {_APP_COLS} FROM applications WHERE mobile = %s "
        "ORDER BY submitted_at DESC",
        (mobile,),
    )


def get_app_by_no(app_no: str) -> dict | None:
    """Single application by application number."""
    return execute_query(
        f"SELECT {_APP_COLS} FROM applications WHERE application_no = %s",
        (app_no,),
        fetch="one",
    )


def has_active_application(mobile: str) -> dict | None:
    """Return the live (PENDING/APPROVED/DEEMED_APPROVED) application, or None."""
    return execute_query(
        "SELECT id, application_no, status FROM applications "
        "WHERE mobile = %s AND status IN %s "
        "ORDER BY submitted_at DESC LIMIT 1",
        (mobile, config.ACTIVE_STATUSES),
        fetch="one",
    )


def get_decision_note(app_id: int) -> str:
    """The officer's reason for the most recent APPROVED/REJECTED decision."""
    row = execute_query(
        "SELECT note FROM audit_log WHERE application_id = %s "
        "AND action IN ('APPROVED','REJECTED') ORDER BY at DESC LIMIT 1",
        (app_id,),
        fetch="one",
        dict_cursor=False,
    )
    return (row[0] or "") if row else ""


def get_otp_count_in_window(mobile: str, window_seconds: int) -> int:
    """Count OTPs sent to this mobile in the last `window_seconds` seconds."""
    from db.pool import get_conn, release_conn
    from domain.time import now_ist
    from datetime import timedelta
    cutoff = now_ist() - timedelta(seconds=window_seconds)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM otps WHERE mobile = %s AND created_at >= %s",
            (mobile, cutoff),
        )
        return cur.fetchone()[0]
    finally:
        cur.close()
        release_conn(conn)


# ── Write operations ──────────────────────────────────────────────────────────

def insert_otp(mobile: str, code: str, created_at) -> None:
    """Persist a new OTP row."""
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO otps (mobile, code, created_at) VALUES (%s, %s, %s)",
            (mobile, code, created_at),
        )
        cur.close()


def get_latest_otp(mobile: str) -> tuple | None:
    """Return (code, created_at) for the most recent OTP, or None."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT code, created_at FROM otps WHERE mobile = %s ORDER BY id DESC LIMIT 1",
            (mobile,),
        )
        return cur.fetchone()
    finally:
        cur.close()
        release_conn(conn)


def insert_application(mobile: str, app_no: str, cleaned: dict, submitted_at) -> int:
    """Insert a validated application row. Returns the new application id."""
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO applications
               (application_no, applicant_name, mobile, dob, gender, marital_status,
                husband_name, husband_employer, village, block, bank_account, ifsc,
                doc_path, status, submitted_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING',%s)
               RETURNING id""",
            (
                app_no,
                cleaned["applicant_name"],
                mobile,
                cleaned["dob"],
                cleaned["gender"],
                cleaned["marital_status"],
                cleaned["husband_name"],
                cleaned["husband_employer"],
                cleaned["village"],
                cleaned["block"],
                cleaned["bank_account"],
                cleaned["ifsc"],
                cleaned["doc_path"],
                submitted_at,
            ),
        )
        new_id = cur.fetchone()[0]
        # Ensure status-portal account exists (password = DOB as DDMMYYYY).
        portal_pass = cleaned["dob"].strftime("%d%m%Y")
        cur.execute("SELECT count(*) FROM portal_users WHERE mobile = %s", (mobile,))
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO portal_users (mobile, password_hash) VALUES (%s, %s)",
                (mobile, hashlib.sha256(portal_pass.encode()).hexdigest()),
            )
        cur.close()
        return new_id


def withdraw_application_row(mobile: str, application_no: str, decided_at) -> dict:
    """Set status=WITHDRAWN on a PENDING row. Returns outcome dict."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE applications SET status='WITHDRAWN', decided_at=%s, decided_by='APPLICANT' "
            "WHERE application_no=%s AND mobile=%s AND status='PENDING' "
            "RETURNING id, application_no",
            (decided_at, application_no, mobile),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.execute(
                "SELECT status FROM applications WHERE application_no=%s AND mobile=%s",
                (application_no, mobile),
            )
            existing = cur.fetchone()
            if not existing:
                return {"error": "Application not found for this mobile."}
            return {
                "error": "Only PENDING applications can be withdrawn. "
                         f"Current status: {existing[0]}."
            }
        from domain.audit import write_audit
        write_audit(cur, row[0], "WITHDRAW", f"applicant:{mobile}")
        conn.commit()
        cur.close()
        return {"success": True, "application_no": row[1], "new_status": "WITHDRAWN"}
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)
