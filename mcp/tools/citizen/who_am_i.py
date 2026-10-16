"""tools/citizen/who_am_i.py — Identity + session status tool."""
import time
from auth import citizen_mobile, session_expires_at, SIGN_IN_REQUIRED
from db.citizen import has_active_application
from middleware.masking import mask_mobile
import config


def register(mcp):
    @mcp.tool()
    def who_am_i() -> dict:
        """WHEN: start of every conversation, or when citizen seems confused about sign-in status.
        Returns signed-in mobile (masked), active application if any, and session seconds left.
        Takes no arguments.
        """
        mobile = citizen_mobile()
        if not mobile:
            return SIGN_IN_REQUIRED

        exp = session_expires_at()
        secs_left = max(0, exp - int(time.time())) if exp else None
        active = has_active_application(mobile)

        result: dict = {
            "signed_in_as":        mask_mobile(mobile),
            "session_seconds_left": secs_left,
            "has_active_application": bool(active),
        }

        # Session expiry warning — kiosk users need this
        if secs_left is not None and secs_left < 300:
            result["session_warning"] = (
                f"Your session expires in {secs_left // 60} minutes. "
                "Complete your work soon."
            )

        if active:
            result["active_application"] = {
                "application_no": active["application_no"],
                "status":         active["status"],
            }
            result["next_step"] = {
                "action": "ask_question",
                "field":  "intent",
                "prompt": (
                    f"Aap signed in hain. Aapki ek active application hai: "
                    f"{active['application_no']} ({active['status']}). "
                    "Kya aap iska status dekhna chahte hain ya kuch aur?"
                ),
                "options": ["Status dekhna hai", "Application wapas leni hai"],
            }
        else:
            result["next_step"] = {
                "action": "ask_question",
                "field":  "intent",
                "prompt": "Aap signed in hain. Kya aap naya pension apply karna chahte hain ya purani application check karni hai?",
                "options": ["Naya apply karna hai", "Purani application check karni hai"],
            }

        return result
