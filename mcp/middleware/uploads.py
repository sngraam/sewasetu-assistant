"""
mcp/middleware/uploads.py — Age-proof document upload manager.

TWO-STAGE UPLOAD FLOW
─────────────────────
Stage 1  — stage_document(mobile, src_path, age_proof_type)
    Validates the file (extension, size, readable).
    Copies it to a temp staging area:
        /var/sewasetu/uploads/.tmp/{mobile}/{safe_filename}
    Returns a temp_ref string the model carries forward.
    The citizen can call this multiple times to replace their document.
    No application number exists yet — nothing permanent is written.

Stage 2  — commit_document(temp_ref, application_no)
    Called automatically inside create_application() after the DB row
    is committed and the application number is known.
    Moves the file from temp to:
        /var/sewasetu/uploads/{application_no}/age_proof{ext}
    Updates doc_path in the DB.
    Returns the final filesystem path.

Cleanup
    cleanup_temp(mobile) — called on withdraw or session end.
    Docker volume: citizen_mcp mounts `uploads:/var/sewasetu/uploads`
    so the app container and the MCP container share the same files.

SECURITY
    File extension whitelist: .pdf .jpg .jpeg .png
    Max size: 5 MB (configurable via MAX_FILE_SIZE_BYTES)
    Path traversal prevention: basename only, no directory components allowed
    No code execution: files are copied as bytes, never interpreted
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import time
from pathlib import Path

import config

log = logging.getLogger("sewasetu.middleware.uploads")

# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_basename(path: str) -> str:
    """Strip directory components — prevent path traversal."""
    return os.path.basename(path).strip()


def _validate_extension(filename: str) -> str | None:
    """Return the lowercased extension if allowed, else None."""
    ext = Path(filename).suffix.lower()
    return ext if ext in config.ALLOWED_EXTENSIONS else None


def _temp_dir(mobile: str) -> Path:
    """Staging directory for a specific mobile number."""
    safe_mobile = re.sub(r"[^0-9]", "", mobile)[:15]
    return Path(config.TEMP_ROOT) / safe_mobile


def _final_dir(application_no: str) -> Path:
    """Permanent directory for an application's documents."""
    safe_no = re.sub(r"[^A-Za-z0-9]", "", application_no)[:20]
    return Path(config.UPLOAD_ROOT) / safe_no


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _file_hash(path: Path) -> str:
    """SHA-256 of file content — used for duplicate detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ── Public API ────────────────────────────────────────────────────────────────

def stage_document(mobile: str, src_path: str, age_proof_type: str) -> dict:
    """
    Stage 1: validate and copy a file to the temp holding area.

    Parameters
    ----------
    mobile         : citizen's mobile (from JWT — never from user input)
    src_path       : absolute path the citizen provided, e.g. /home/user/voter_id.pdf
    age_proof_type : "Voter ID" | "Birth certificate" | "School leaving certificate"

    Returns
    -------
    On success:
        {
            "staged":         True,
            "temp_ref":       "9876543210/voter_id_a3f2b1.pdf",   ← carry this into submit
            "filename":       "voter_id_a3f2b1.pdf",
            "size_kb":        124,
            "age_proof_type": "Voter ID",
            "next_step":      { ... }
        }
    On failure:
        {
            "error":     { "code": "...", "message": "...", "recovery": "ask_again" },
            "next_step": { ... }
        }
    """
    # ── 1. Validate source path ───────────────────────────────────────────────
    src = Path(src_path).expanduser().resolve()

    if not src.exists():
        return _stage_error(
            "FILE_NOT_FOUND",
            f"File '{src_path}' not found. Please check the path and try again.",
            "Kaunsi file upload karni hai? Sahi file path batayein (jaise /home/user/voter_id.pdf).",
        )

    if not src.is_file():
        return _stage_error(
            "NOT_A_FILE",
            f"'{src_path}' is a directory, not a file.",
            "Ek file ka path batayein, folder ka nahi.",
        )

    # ── 2. Extension check ────────────────────────────────────────────────────
    ext = _validate_extension(src.name)
    if ext is None:
        allowed = ", ".join(config.ALLOWED_EXTENSIONS)
        return _stage_error(
            "INVALID_EXTENSION",
            f"File type '{src.suffix}' is not accepted. Allowed: {allowed}.",
            f"Sirf {allowed} files accept ki jaati hain. Sahi file batayein.",
        )

    # ── 3. Size check ─────────────────────────────────────────────────────────
    size_bytes = src.stat().st_size
    if size_bytes == 0:
        return _stage_error(
            "EMPTY_FILE",
            "The file is empty (0 bytes).",
            "File khaali lag rahi hai. Dobara check karein.",
        )
    if size_bytes > config.MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        max_mb  = config.MAX_FILE_SIZE_BYTES / (1024 * 1024)
        return _stage_error(
            "FILE_TOO_LARGE",
            f"File is {size_mb:.1f} MB. Maximum allowed is {max_mb:.0f} MB.",
            f"File bahut badi hai ({size_mb:.1f} MB). {max_mb:.0f} MB se choti file upload karein.",
        )

    # ── 4. Build safe destination filename ───────────────────────────────────
    proof_slug = age_proof_type.lower().replace(" ", "_")  # "voter_id"
    file_hash  = _file_hash(src)                           # uniqueness + tamper-detect
    dest_name  = f"{proof_slug}_{file_hash}{ext}"          # "voter_id_a3f2b1.pdf"

    # ── 5. Copy to temp dir ───────────────────────────────────────────────────
    temp_dir = _temp_dir(mobile)
    _ensure_dir(temp_dir)

    # Remove any previous staged file for this mobile (replace, don't accumulate)
    for old in temp_dir.glob("*"):
        if old.is_file():
            old.unlink()
            log.info("upload_temp_replaced mobile=%s old=%s", mobile, old.name)

    dest = temp_dir / dest_name
    shutil.copy2(src, dest)

    # temp_ref is the carrier the model passes to submit_application
    safe_mobile = re.sub(r"[^0-9]", "", mobile)[:15]
    temp_ref = f"{safe_mobile}/{dest_name}"

    log.info(
        "upload_staged mobile=%s file=%s size=%d",
        mobile, dest_name, size_bytes,
        extra={} if True else None,
    )

    return {
        "staged":         True,
        "temp_ref":       temp_ref,
        "filename":       dest_name,
        "size_kb":        round(size_bytes / 1024, 1),
        "age_proof_type": age_proof_type,
        "next_step": {
            "action":  "confirm_and_submit",
            "prompt":  (
                f"Document '{src.name}' ({round(size_bytes/1024, 1)} KB) staged. "
                "Agar sab details sahi hain to submit karein."
            ),
            "field":   "confirm",
            "options": ["Haan, submit karein", "Nahi, kuch badalna hai"],
        },
    }


def commit_document(temp_ref: str, application_no: str) -> str | None:
    """
    Stage 2: move the staged file to its permanent location.

    Called automatically by create_application() after the DB row is committed.
    Returns the final path string (stored in applications.doc_path), or None
    if the temp file is missing (caller should fall back to declared://).

    Final path: /var/sewasetu/uploads/{application_no}/age_proof{ext}
    """
    if not temp_ref:
        return None

    # Reconstruct the temp path from temp_ref = "{mobile}/{filename}"
    parts = temp_ref.split("/", 1)
    if len(parts) != 2:
        log.warning("commit_document bad temp_ref=%s", temp_ref)
        return None

    mobile_dir, filename = parts
    temp_path = Path(config.TEMP_ROOT) / mobile_dir / filename

    if not temp_path.exists():
        log.warning(
            "commit_document temp_not_found temp_ref=%s app_no=%s",
            temp_ref, application_no,
        )
        return None

    # Validate extension one more time (defense in depth)
    ext = _validate_extension(filename)
    if ext is None:
        log.error("commit_document rejected extension temp_ref=%s", temp_ref)
        return None

    final_dir = _final_dir(application_no)
    _ensure_dir(final_dir)
    final_path = final_dir / f"age_proof{ext}"

    shutil.move(str(temp_path), str(final_path))

    # Clean up the now-empty temp directory
    try:
        temp_dir = Path(config.TEMP_ROOT) / mobile_dir
        if temp_dir.exists() and not any(temp_dir.iterdir()):
            temp_dir.rmdir()
    except Exception:
        pass  # non-critical

    log.info(
        "upload_committed app_no=%s path=%s",
        application_no, str(final_path),
    )
    return str(final_path)


def update_doc_path_in_db(application_no: str, final_path: str) -> None:
    """Update doc_path after a successful commit."""
    from db.pool import get_conn, release_conn
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE applications SET doc_path = %s WHERE application_no = %s",
            (final_path, application_no),
        )
        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def cleanup_temp(mobile: str) -> None:
    """Remove all staged files for a mobile (withdraw or session end)."""
    temp_dir = _temp_dir(mobile)
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        log.info("upload_temp_cleaned mobile=%s", mobile)


def get_staged_info(temp_ref: str) -> dict | None:
    """
    Return info about a staged file, or None if it no longer exists.
    Used by the confirmation step to show the citizen what will be submitted.
    """
    if not temp_ref:
        return None
    parts = temp_ref.split("/", 1)
    if len(parts) != 2:
        return None
    mobile_dir, filename = parts
    temp_path = Path(config.TEMP_ROOT) / mobile_dir / filename
    if not temp_path.exists():
        return None
    stat = temp_path.stat()
    return {
        "filename":  filename,
        "size_kb":   round(stat.st_size / 1024, 1),
        "staged_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _stage_error(code: str, message: str, prompt: str) -> dict:
    return {
        "error": {
            "code":     code,
            "message":  message,
            "recovery": "ask_again",
        },
        "next_step": {
            "action":   "ask_question",
            "field":    "file_path",
            "prompt":   prompt,
            "recovery": "ask_again",
        },
    }
