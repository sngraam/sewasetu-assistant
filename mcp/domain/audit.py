"""mcp/domain/audit.py — Write audit log entries."""
from __future__ import annotations
from domain.time import now_ist


def write_audit(cur, app_id: int, action: str, actor: str, note: str = "") -> None:
    """Insert an audit entry using an already-open cursor (caller commits)."""
    cur.execute(
        "INSERT INTO audit_log (application_id, action, actor, note, at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (app_id, action, actor, note, now_ist()),
    )
