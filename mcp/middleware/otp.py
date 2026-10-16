"""
mcp/middleware/otp.py — OTP generation, rate-limiting, and verification.

Rate limit: max OTP_MAX_PER_WINDOW OTPs per mobile per OTP_WINDOW_SECONDS.
This prevents SMS spam and brute-force attacks.
"""
from __future__ import annotations

import logging
import random

import config
import requests as http_requests

from db.citizen import (
    get_otp_count_in_window,
    insert_otp,
    get_latest_otp,
)
from domain.time import now_ist

log = logging.getLogger("sewasetu.middleware.otp")


def send_otp(mobile: str) -> dict:
    """
    Generate and send a 6-digit OTP to the mobile number.

    Returns:
        {"sent": True, "mobile": mobile}  on success
        {"error": "...", "retry_after_seconds": N}  if rate-limited
    """
    # Rate-limit check
    count = get_otp_count_in_window(mobile, config.OTP_WINDOW_SECONDS)
    if count >= config.OTP_MAX_PER_WINDOW:
        log.warning("otp_rate_limited mobile=%s count=%d", mobile, count)
        return {
            "error": (
                f"Too many OTP requests. Maximum {config.OTP_MAX_PER_WINDOW} OTPs "
                f"allowed per {config.OTP_WINDOW_SECONDS // 60} minutes."
            ),
            "retry_after_seconds": config.OTP_WINDOW_SECONDS,
        }

    code = "%06d" % random.randint(0, 999999)
    insert_otp(mobile, code, now_ist())

    try:
        http_requests.post(
            config.SMS_GATEWAY_URL + "/api/send",
            json={
                "to":   mobile,
                "text": f"Your Sewa Setu OTP is {code}. Valid for 5 minutes.",
            },
            timeout=5,
        )
        log.info("otp_sent mobile=%s", mobile)
    except Exception as exc:
        log.warning("otp_sms_failed mobile=%s error=%s", mobile, exc)
        # OTP is in DB even if SMS fails — dev can read it from /__gateway/

    return {"sent": True, "mobile": mobile}


def verify_otp(mobile: str, otp: str) -> dict:
    """
    Verify the OTP the citizen typed.

    Returns:
        {"verified": True, "mobile": mobile}
        {"verified": False, "error": "...", "action": "resend" | "stop"}
    """
    row = get_latest_otp(mobile)
    if not row:
        return {
            "verified": False,
            "error":    "No OTP found for this mobile number.",
            "action":   "resend",
        }

    stored_code, created_at = row
    age_seconds = (now_ist() - created_at).total_seconds()

    if age_seconds > config.OTP_VALIDITY_SECONDS:
        return {
            "verified": False,
            "error":    "OTP has expired. Please request a new one.",
            "action":   "resend",
        }

    if stored_code != (otp or "").strip():
        return {
            "verified": False,
            "error":    "Incorrect OTP. Please check and try again.",
            "action":   "ask_again",
        }

    log.info("otp_verified mobile=%s", mobile)
    return {"verified": True, "mobile": mobile}
