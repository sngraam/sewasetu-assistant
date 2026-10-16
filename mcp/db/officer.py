"""
mcp/db/officer.py — All officer-facing database queries.

Pagination, dossier assembly, duplicate detection, and decision writing.
No business logic. Import from domain/ for flag computation.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import psycopg2.extras

import config
from db.pool import db_conn, execute_query, get_conn, release_conn, row_to_dict

log = logging.getLogger("sewasetu.db.officer")

_APP_COLS = (
    "id, application_no, applicant_name, mobile, dob, gender, marital_status, "
    "husband_name, village, block, bank_account, ifsc, doc_path, "
    "status, submitted_at, decided_at, decided_by"
)


# Read queries 

def list_applications(
    status: str = "PENDING",
    block: str = "",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """
    Paginated list of applications, oldest first. Safe for 100 k rows.
    """
    page      = max(1, int(page))
    page_size = max(1, min(int(page_size), 20))

    clauses: list[str] = []
    params:  list      = []
    if status and status.upper() != "ALL":
        clauses.append("status = %s")
        params.append(status.upper())
    if block:
        clauses.append("block = %s")
        params.append(block)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT count(*) AS n FROM applications{where}", params)
        total = cur.fetchone()["n"]

        cur.execute(
            f"SELECT id, application_no, applicant_name, village, block, "
            f"status, submitted_at, doc_path FROM applications{where} "
            f"ORDER BY submitted_at ASC LIMIT %s OFFSET %s",
            params + [page_size, (page - 1) * page_size],
        )
        rows = []
        for r in cur.fetchall():
            d = row_to_dict(r)
            d["declared_only"] = str(d.get("doc_path") or "").startswith(config.DECLARED_PREFIX)
            d.pop("doc_path", None)   # officers use get_dossier for the full record
            rows.append(d)
        cur.close()
        return {
            "total_matching": total,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total,
            "applications": rows,
        }
    finally:
        release_conn(conn)


def get_application_by_no(app_no: str) -> dict | None:
    """
    Full application row for the officer dossier.
    """
    return execute_query(
        f"SELECT {_APP_COLS} FROM applications WHERE application_no = %s",
        (app_no,),
        fetch="one",
    )


def get_audit_trail(app_id: int, limit: int = 20) -> list[dict]:
    return execute_query(
        "SELECT action, actor, note, at FROM audit_log "
        "WHERE application_id = %s ORDER BY at DESC LIMIT %s",
        (app_id, limit),
    )


def find_possible_duplicates(app_id: int, bank_account: str,
                              applicant_name: str, dob) -> list[dict]:
    """
    Other live applications sharing the bank account OR name+DOB.
    """
    return execute_query(
        "SELECT application_no, applicant_name, mobile, status, "
        "(bank_account = %s) AS same_bank_account, "
        "(applicant_name = %s AND dob = %s) AS same_name_and_dob "
        "FROM applications WHERE id <> %s AND status IN %s "
        "AND (bank_account = %s OR (applicant_name = %s AND dob = %s)) LIMIT 5",
        (bank_account, applicant_name, dob, app_id,
         config.ACTIVE_STATUSES,
         bank_account, applicant_name, dob),
    )


def dashboard_stats() -> dict:
    """
    Counts by status, pending by block, overdue count.
    """
    from domain.time import now_ist
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT status, count(*) AS n FROM applications GROUP BY status")
        by_status = {r["status"]: r["n"] for r in cur.fetchall()}

        cur.execute(
            "SELECT block, count(*) AS n FROM applications WHERE status='PENDING' "
            "GROUP BY block ORDER BY n DESC"
        )
        by_block = {r["block"]: r["n"] for r in cur.fetchall()}

        cutoff = now_ist() - timedelta(days=config.SLA_DAYS)
        cur.execute(
            "SELECT count(*) AS n FROM applications WHERE status='PENDING' AND submitted_at < %s",
            (cutoff,),
        )
        overdue = cur.fetchone()["n"]

        cur.execute("SELECT count(*) AS n FROM applications")
        total = cur.fetchone()["n"]
        cur.close()

        return {
            "total_applications": total,
            "by_status": by_status,
            "pending_by_block": by_block,
            "overdue_pending_beyond_sla_days": overdue,
            "sla_days": config.SLA_DAYS,
            "valid_blocks": config.BLOCKS,
            "agent_blocks": config.AGENT_BLOCKS,
        }
    finally:
        release_conn(conn)


# Write operations 

def decide_application(
    application_no: str,
    new_status: str,
    decided_by: str,
    note: str,
    decided_at,
) -> dict:
    """Set APPROVED or REJECTED on a PENDING application. Returns outcome dict."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "UPDATE applications SET status=%s, decided_at=%s, decided_by=%s "
            "WHERE application_no=%s AND status='PENDING' "
            "RETURNING id, application_no, applicant_name",
            (new_status, decided_at, decided_by, application_no),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            cur.execute(
                "SELECT status FROM applications WHERE application_no=%s",
                (application_no,),
            )
            existing = cur.fetchone()
            if not existing:
                return {"error": f"Application {application_no} not found."}
            return {
                "error": f"Only PENDING applications can be decided. "
                         f"This application is already {existing['status']}.",
                "current_status": existing["status"],
            }
        from domain.audit import write_audit
        write_audit(cur, row["id"], new_status, f"admin:{decided_by}", note)
        conn.commit()
        cur.close()
        return {
            "success": True,
            "application_no": row["application_no"],
            "applicant_name": row["applicant_name"],
            "new_status": new_status,
            "decided_by": decided_by,
            "decided_at": decided_at.isoformat(),
            "note": note,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)
