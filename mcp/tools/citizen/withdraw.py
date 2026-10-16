"""tools/citizen/withdraw.py — Withdraw a PENDING application."""
from auth import citizen_mobile, SIGN_IN_REQUIRED
from domain.application import withdraw_application
from middleware.uploads import cleanup_temp
from prompts import next_steps as NS


def register(mcp):
    @mcp.tool()
    def withdraw_application(application_no: str) -> dict:
        """WHEN: citizen has explicitly confirmed they want to withdraw their PENDING application.
        Only PENDING applications can be withdrawn. You MUST get explicit confirmation
        ("Haan, wapas lo") BEFORE calling this — it is irreversible.

        Args:
            application_no: Application number to withdraw. Get from my_applications().
        """
        mobile = citizen_mobile()
        if not mobile:
            return SIGN_IN_REQUIRED

        if not application_no or not application_no.strip():
            return {
                "error": {
                    "code":    "MISSING_ARG",
                    "field":   "application_no",
                    "message": "Application number is required.",
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action":  "call_tool",
                    "tool":    "my_applications",
                    "prompt":  "Pehle my_applications se list dekhte hain.",
                },
            }

        result = withdraw_application(mobile, application_no.strip())

        if result.get("success"):
            # Clean up any staged document for this mobile on withdrawal
            cleanup_temp(mobile)
            return {
                **result,
                "next_step": NS.withdrawn_ok(application_no),
            }
        else:
            return {
                **result,
                "next_step": {
                    "action": "inform",
                    "prompt": result.get("error", "Application wapas nahi ho saki."),
                    "recovery": "stop",
                },
            }
