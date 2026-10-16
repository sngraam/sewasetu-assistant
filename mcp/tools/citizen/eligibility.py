"""tools/citizen/eligibility.py — Pre-application eligibility check."""
import config
from auth import citizen_mobile, SIGN_IN_REQUIRED
from db.citizen import has_active_application
from domain.validation import parse_dob, age_on
from domain.time import now_ist
from prompts import next_steps as NS


def register(mcp):
    @mcp.tool()
    def check_eligibility(dob: str, block: str) -> dict:
        """WHEN: citizen wants to apply and you have their DOB and block.
        Call this BEFORE collecting name, bank details, etc. Fails fast if ineligible.

        Args:
            dob:   Date of birth as DD/MM/YYYY. Example: 15/03/1955.
            block: Block name. One of: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua.
        """
        mobile = citizen_mobile()
        if not mobile:
            return SIGN_IN_REQUIRED

        errors: list[str] = []

        # ── Age check ─────────────────────────────────────────────────────────
        dob_date = parse_dob(dob)
        if dob_date is None:
            return {
                "eligible": False,
                "error": {
                    "code":        "INVALID_DOB",
                    "message":     "Date of birth format is incorrect.",
                    "recovery":    "ask_again",
                },
                "next_step": NS.ASK_DOB,
            }

        age = age_on(dob_date, now_ist().date())
        if age < config.MIN_AGE:
            return {
                "eligible": False,
                "error": {
                    "code":    "AGE_BELOW_MINIMUM",
                    "message": f"Applicant is {age} years old. Minimum age is {config.MIN_AGE}.",
                    "recovery": "stop",
                },
                "next_step": NS.ineligible_age(age),
            }

        # ── Block check ───────────────────────────────────────────────────────
        block_clean = (block or "").strip()
        if block_clean not in config.BLOCKS:
            return {
                "eligible": False,
                "error": {
                    "code":    "INVALID_BLOCK",
                    "message": f"'{block_clean}' is not a valid block.",
                    "recovery": "ask_again",
                },
                "next_step": NS.ASK_BLOCK,
            }

        if block_clean not in config.AGENT_BLOCKS:
            return {
                "eligible": False,
                "error": {
                    "code":    "BLOCK_NOT_IN_PILOT",
                    "message": f"Block '{block_clean}' is not served by the AI channel.",
                    "recovery": "redirect",
                },
                "next_step": NS.ineligible_block(block_clean),
            }

        # ── Scheme window check ───────────────────────────────────────────────
        if now_ist() > config.SCHEME_DEADLINE:
            return {
                "eligible": False,
                "error": {
                    "code":    "SCHEME_CLOSED",
                    "message": "Application window has closed.",
                    "recovery": "stop",
                },
                "next_step": NS.SCHEME_CLOSED,
            }

        # ── Duplicate active application check ───────────────────────────────
        active = has_active_application(mobile)
        if active:
            return {
                "eligible": False,
                "error": {
                    "code":           "DUPLICATE_ACTIVE",
                    "message":        f"Active application {active['application_no']} ({active['status']}) already exists.",
                    "application_no": active["application_no"],
                    "status":         active["status"],
                    "recovery":       "call_tool",
                },
                "next_step": NS.DUPLICATE_ACTIVE,
            }

        # ── All checks passed ─────────────────────────────────────────────────
        next_step = dict(NS.ELIGIBLE_PROCEED)
        return {
            "eligible": True,
            "collected": {
                "dob":   dob,        # already known — model must NOT ask again
                "block": block_clean,
            },
            "applicant_age": age,
            "next_step": next_step,
        }
