"""tools/officer/dossier.py — get_dossier tool."""
import config
from auth import officer_name
from domain.application import build_dossier
from prompts import next_steps as NS

_AUTH_ERROR = {
    "error": {"code": "NOT_AUTHENTICATED", "message": "Officer not signed in.", "recovery": "stop"},
    "next_step": {"action": "inform", "prompt": "Sign in karein pehle."},
}


def register(mcp):
    @mcp.tool()
    def get_dossier(application_no: str) -> dict:
        """WHEN: officer wants to inspect one application before deciding.
        Always call this before decide_application.
        Returns full record, flags, and complete audit trail.

        Flags:
            age_ok              — applicant meets minimum age at submission
            declared_only       — age proof declared, no file uploaded
            age_proof_note      — plain-English guidance
            possible_duplicates — other live apps with same bank account or name+DOB
            sla_overdue         — pending beyond SLA_DAYS
            days_pending        — calendar days since submission

        Args:
            application_no: Application number. Example: SSP26100001. Get from list_pending().
        """
        officer = officer_name()
        if not officer:
            return _AUTH_ERROR

        if not application_no or not application_no.strip():
            return {
                "error": {
                    "code":    "MISSING_ARG",
                    "field":   "application_no",
                    "message": "Application number is required.",
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action": "call_tool",
                    "tool":   "list_pending",
                    "prompt": "list_pending() se application number lo.",
                },
            }

        dossier = build_dossier(application_no.strip())
        if not dossier:
            return {
                "error": {
                    "code":    "NOT_FOUND",
                    "message": f"Application {application_no} not found.",
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action": "call_tool",
                    "tool":   "list_pending",
                    "prompt": "Application number sahi nahi. list_pending() se dekhein.",
                },
            }

        dossier["signed_in_as"] = officer

        # Compile warnings for the officer
        flags    = dossier.get("flags", {})
        warnings = []
        if not flags.get("age_ok"):
            warnings.append("AGE_CHECK_FAILED — applicant may not meet minimum age")
        if flags.get("declared_only"):
            warnings.append("DECLARED_ONLY — physical document must be verified before approving")
        if flags.get("possible_duplicates"):
            warnings.append(
                f"DUPLICATE_RISK — {len(flags['possible_duplicates'])} other live application(s) "
                "share the same bank account or name+DOB"
            )
        if flags.get("sla_overdue"):
            warnings.append(
                f"SLA_BREACHED — pending {flags.get('days_pending', 0)} days "
                f"(SLA is {config.SLA_DAYS} days)"
            )

        dossier["officer_warnings"] = warnings

        # Decide what the model should do next
        declared_only = flags.get("declared_only", False)
        confirm_note  = ", confirmed_original_seen=True" if declared_only else ""

        dossier["next_step"] = {
            "action":   "inform",
            "prompt":   NS.officer_dossier_warnings(warnings)["prompt"],
            "tool_hint": (
                f"decide_application(\"{application_no}\", \"APPROVE\" or \"REJECT\", "
                f"reason{confirm_note})"
            ),
        }

        return dossier
