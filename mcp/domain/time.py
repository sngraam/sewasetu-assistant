"""mcp/domain/time.py — Time helpers. All times are IST."""
from datetime import datetime
import config


def now_ist() -> datetime:
    """Current time in IST, timezone-stripped (matches PostgreSQL TIMESTAMP)."""
    return datetime.now(config.IST).replace(tzinfo=None)


def now_str() -> str:
    return now_ist().isoformat()
