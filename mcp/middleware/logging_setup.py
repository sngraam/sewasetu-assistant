"""
mcp/middleware/logging_setup.py — Structured JSON logging.

In production every log line is a JSON object so log aggregators (CloudWatch,
Datadog, Loki, etc.) can index on application_no, officer, action, etc.

In dev (LOG_FORMAT=text) plain text is used for readability.
"""
from __future__ import annotations

import logging
import os
import sys
import json
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    LEVEL_MAP = {
        logging.DEBUG:    "debug",
        logging.INFO:     "info",
        logging.WARNING:  "warning",
        logging.ERROR:    "error",
        logging.CRITICAL: "critical",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "level":   self.LEVEL_MAP.get(record.levelno, "info"),
            "logger":  record.name,
            "message": record.getMessage(),
        }

        # Structured fields passed as `extra={}` in log calls
        for key in ("application_no", "mobile", "officer", "action", "block"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure(service: str) -> None:
    """Call once at server startup. Configures root logger."""
    log_format = os.environ.get("LOG_FORMAT", "json").lower()
    log_level  = os.environ.get("LOG_LEVEL",  "INFO").upper()

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove any existing handlers (e.g. basicConfig leftover)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(root.level)

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )

    root.addHandler(handler)
    logging.getLogger(f"sewasetu.{service}").info(
        "Logging initialised", extra={"action": "startup", "service": service}
    )
