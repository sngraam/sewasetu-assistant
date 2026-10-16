"""
mcp/domain/validation.py — Application validation rules.

Mirrors app.py's validate_application() exactly so every channel
(web portal, MCP) enforces identical rules.
"""
from __future__ import annotations

import re
from datetime import datetime, date

import config
from domain.time import now_ist


def parse_dob(raw: str) -> date | None:
    """Parse DD/MM/YYYY → date, or None on failure."""
    try:
        return datetime.strptime((raw or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def age_on(dob: date, on: date) -> int:
    """Age in whole years on a given date."""
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def validate_application(data: dict, doc_path: str = "") -> tuple[list[str], dict]:
    """
    Validate a complete application.

    Returns (errors, cleaned) where:
      errors  — list of plain-language problem strings (empty = valid)
      cleaned — normalised values ready for insertion
    """
    errors: list[str] = []

    cleaned = {
        "applicant_name":   (data.get("applicant_name") or "").strip()[:100],
        "village":          (data.get("village") or "").strip(),
        "block":            (data.get("block") or "").strip(),
        "gender":           (data.get("gender") or "").strip(),
        "marital_status":   (data.get("marital_status") or "").strip(),
        "husband_name":     (data.get("husband_name") or "").strip(),
        "husband_employer": "",
        "bank_account":     re.sub(r"[\s\-]", "", data.get("bank_account") or ""),
        "ifsc":             re.sub(r"[\s\-]", "", (data.get("ifsc") or "")).upper(),
        "doc_path":         doc_path or "",
        "dob":              None,
    }

    # Required fields
    for label, key in (
        ("full name",    "applicant_name"),
        ("village",      "village"),
        ("block",        "block"),
        ("bank account", "bank_account"),
    ):
        if not cleaned[key]:
            errors.append(f"{label} is required")

    # Block
    if cleaned["block"] and cleaned["block"] not in config.BLOCKS:
        errors.append("block must be one of: " + ", ".join(config.BLOCKS))

    # Bank account
    if cleaned["bank_account"] and not re.fullmatch(r"\d{9,18}", cleaned["bank_account"]):
        errors.append("bank account number must be 9 to 18 digits")

    # IFSC
    if cleaned["ifsc"] and not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", cleaned["ifsc"]):
        errors.append("IFSC must be 11 characters, e.g. SBIN0003077")

    # Date of birth
    dob = parse_dob(data.get("dob"))
    if dob is None:
        errors.append("date of birth must be given as DD/MM/YYYY")
    else:
        cleaned["dob"] = dob
        if age_on(dob, now_ist().date()) < config.MIN_AGE:
            errors.append(f"applicant must be {config.MIN_AGE} years of age or above")

    # Age proof document
    if not cleaned["doc_path"]:
        errors.append("age proof document is required")

    # Scheme window
    if now_ist() > config.SCHEME_DEADLINE:
        errors.append(
            "the application window closed on 31 October 2026; "
            "new applications are no longer accepted"
        )

    return errors, cleaned
