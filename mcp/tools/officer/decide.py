"""tools/officer/decide.py — decide_application tool."""
import logging

from auth import officer_name
from db.officer import decide_application as db_decide
from domain.application import build_dossier
from domain.time import now_ist
from prompts import next_steps as NS

log = logging.getLogger("sewasetu.tools.officer.decide")

_AUTH_ERROR = {
    "error": {"code": "NOT_AUTHENTICATED", "message": "Officer not signed in.", "recovery": "stop"},
    "next_step": {"action": "inform", "prompt": "Sign in karein pehle."},
}


def register(mcp):
    @mcp.tool()
    def decide_application(
        application_no:         str,
        decision:               str,
        reason:                 str,
        confirmed_original_seen: bool = False,
    ) -> dict:
        """WHEN: officer has read the dossier and is ready to approve or reject.
        Always call get_dossier first. This action is IRREVERSIBLE.
        Officer identity comes from the sign-in token — never from tool arguments.

        Args:
            application_no:          Application number. Example: SSP26100001.
            decision:                "APPROVE" or "REJECT" (case-insensitive).
            reason:                  Reason for the decision. REQUIRED for REJECT.
                                     Recommended for APPROVE (recorded in audit log).
            confirmed_original_seen: Set True when approving a DECLARED_ONLY application
                                     to confirm physical document was verified.
        """
        officer = officer_name()
        if not officer:
            return _AUTH_ERROR

        decision_upper = (decision or "").strip().upper()
        if decision_upper not in ("APPROVE", "REJECT"):
            return {
                "error": {
                    "code":     "INVALID_DECISION",
                    "message":  "Decision must be APPROVE or REJECT.",
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action":  "ask_question",
                    "field":   "decision",
                    "prompt":  "Kya aap APPROVE karna chahte hain ya REJECT? Reason bhi batayein agar reject kar rahe hain.",
                    "options": ["APPROVE", "REJECT"],
                },
            }

        # Reject requires a reason
        if decision_upper == "REJECT" and not (reason or "").strip():
            return {
                "error": {
                    "code":     "MISSING_REASON",
                    "message":  "Rejection reason is required.",
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action":  "ask_question",
                    "field":   "reason",
                    "prompt":  "Rejection ka reason kya hai? Yeh applicant ko dikhega.",
                    "recovery": "ask_again",
                },
            }

        # Declared-only guard — officer must physically verify before approving
        if decision_upper == "APPROVE":
            dossier = build_dossier(application_no)
            if dossier:
                flags = dossier.get("flags", {})
                if flags.get("declared_only") and not confirmed_original_seen:
                    return {
                        "error": {
                            "code":    "DECLARED_ONLY_UNCONFIRMED",
                            "message": "Age proof is DECLARED ONLY — no file was uploaded.",
                            "recovery": "ask_again",
                        },
                        "age_proof_note": flags.get("age_proof_note", ""),
                        "next_step": {
                            "action":  "ask_question",
                            "field":   "confirmed_original_seen",
                            "prompt":  (
                                "Is application mein age proof ka koi file upload nahi hai — "
                                "sirf declaration hai. Kya aapne physical document personally dekha hai? "
                                "(Haan → confirmed_original_seen=True ke saath dobara call karein)"
                            ),
                            "recovery": "ask_again",
                        },
                    }

        new_status = "APPROVED" if decision_upper == "APPROVE" else "REJECTED"
        result = db_decide(
            application_no, new_status, officer,
            (reason or "").strip(), now_ist()
        )

        if result.get("success"):
            log.info(
                "application_decided application_no=%s decision=%s officer=%s",
                application_no, new_status, officer
            )
            return {
                **result,
                "next_step": NS.officer_decided(application_no, new_status),
            }
        else:
            return {
                **result,
                "next_step": {
                    "action": "inform",
                    "prompt": result.get("error", "Decision nahi ho saki."),
                    "current_status": result.get("current_status", "unknown"),
                    "recovery": "stop",
                },
            }
