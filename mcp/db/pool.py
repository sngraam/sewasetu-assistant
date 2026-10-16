"""
mcp/db/pool.py — Shared PostgreSQL connection pool.

Uses psycopg2's ThreadedConnectionPool so all MCP tool calls in the same
process share a fixed-size pool instead of opening a new connection per call.

Usage:
    from db.pool import get_conn, release_conn

    conn = get_conn()
    try:
        cur = conn.cursor()
        ...
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        release_conn(conn)

Or use the context manager helper:

    with db_conn() as conn:
        cur = conn.cursor()
        ...
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool

import config

log = logging.getLogger("sewasetu.db.pool")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _build_pool() -> psycopg2.pool.ThreadedConnectionPool:
    return psycopg2.pool.ThreadedConnectionPool(
        minconn=config.DB_POOL_MIN,
        maxconn=config.DB_POOL_MAX,
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        connect_timeout=5,
    )


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        with _pool_lock:
            if _pool is None or _pool.closed:
                log.info(
                    "Initialising connection pool (min=%d max=%d) → %s:%s/%s",
                    config.DB_POOL_MIN, config.DB_POOL_MAX,
                    config.DB_HOST, config.DB_PORT, config.DB_NAME,
                )
                _pool = _build_pool()
    return _pool


def get_conn() -> psycopg2.extensions.connection:
    """
    Borrow a connection from the pool. Call release_conn() when done.
    """
    return _get_pool().getconn()


def release_conn(conn: psycopg2.extensions.connection) -> None:
    """
    Return a connection to the pool.
    """
    try:
        _get_pool().putconn(conn)
    except Exception as exc:
        log.warning("Could not return connection to pool: %s", exc)


@contextmanager
def db_conn():
    """
    Context manager: borrows a connection, commits on success, rolls back on error.
    """
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def health_check() -> bool:
    """Return True if a DB round-trip succeeds."""
    try:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return True
        finally:
            release_conn(conn)
    except Exception as exc:
        log.error("DB health check failed: %s", exc)
        return False


# Row serialisation

def row_to_dict(row: Any) -> dict:
    """Convert a RealDictCursor row to a plain JSON-serialisable dict."""
    out = dict(row)
    for k, v in out.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
    return out


# Convenience wrapper 

def execute_query(
    sql: str,
    params: tuple = (),
    *,
    fetch: str = "all",   # "all" | "one" | "none"
    dict_cursor: bool = True,
) -> Any:
    """
    Run a SELECT and return rows. Not for writes — use db_conn() for those.
    """
    conn = get_conn()
    try:
        factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=factory) if factory else conn.cursor()
        cur.execute(sql, params)
        if fetch == "one":
            row = cur.fetchone()
            return row_to_dict(row) if row and dict_cursor else row
        elif fetch == "all":
            rows = cur.fetchall()
            return [row_to_dict(r) for r in rows] if dict_cursor else rows
        return None
    finally:
        cur.close()
        release_conn(conn)
