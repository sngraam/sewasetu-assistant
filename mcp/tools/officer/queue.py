"""tools/officer/queue.py — queue_summary and list_pending tools."""
from auth import officer_name
from db.officer import dashboard_stats, list_applications
import config

_AUTH_ERROR = {
    "error": {
        "code":    "NOT_AUTHENTICATED",
        "message": "Officer not signed in.",
        "recovery": "stop",
    },
    "next_step": {
        "action": "inform",
        "prompt": "Aapko Sewa Setu portal par sign in karna hoga. Chat mein username ya password mat batayein.",
    },
}


def register(mcp):

    @mcp.tool()
    def queue_summary() -> dict:
        """WHEN: start of officer session, or to get a fresh overview.
        Returns counts by status, pending by block, overdue count, and pilot blocks.
        Takes no arguments.
        """
        officer = officer_name()
        if not officer:
            return _AUTH_ERROR

        stats = dashboard_stats()
        pending_count = stats.get("by_status", {}).get("PENDING", 0)
        overdue       = stats.get("overdue_pending_beyond_sla_days", 0)

        action_prompt = (
            f"{pending_count} pending application{'s' if pending_count != 1 else ''} waiting."
        )
        if overdue:
            action_prompt += f" ⚠️  {overdue} overdue (beyond {config.SLA_DAYS}-day SLA)."

        return {
            **stats,
            "signed_in_as": officer,
            "next_step": {
                "action": "inform",
                "prompt": action_prompt + " Call list_pending() to see the queue.",
            },
        }

    @mcp.tool()
    def list_pending(page: int = 1, block: str = "") -> dict:
        """WHEN: officer wants to see which applications need a decision.
        Returns 10 PENDING applications per page, oldest first.
        Each row has declared_only=True if no file was uploaded.

        Args:
            page:  Page number (1-based). Default: 1.
            block: Optional block filter. Example: "Sonari". Leave empty for all.
        """
        officer = officer_name()
        if not officer:
            return _AUTH_ERROR

        result = list_applications(status="PENDING", block=block, page=page)
        result["signed_in_as"] = officer

        if not result.get("applications"):
            result["next_step"] = {
                "action": "inform",
                "prompt": "Is page par koi pending application nahi hai.",
            }
        else:
            has_more = result.get("has_more", False)
            result["next_step"] = {
                "action": "inform",
                "prompt": (
                    f"{result['total_matching']} pending applications hain. "
                    "Ek application ka dossier dekhne ke liye get_dossier(application_no) call karein."
                    + (f" Next page ke liye list_pending(page={page+1}) call karein." if has_more else "")
                ),
            }

        return result
