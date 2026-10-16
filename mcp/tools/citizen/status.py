"""tools/citizen/status.py — my_applications and get_application tools."""
import config
from auth import citizen_mobile, SIGN_IN_REQUIRED
from db.citizen import get_apps_by_mobile, get_app_by_no, get_decision_note
from middleware.masking import mask_account, mask_mobile
from prompts import next_steps as NS


def register(mcp):

    @mcp.tool()
    def my_applications() -> dict:
        """WHEN: citizen wants to see all their applications or check status.
        Returns list of all applications with masked bank accounts.
        Takes no arguments.
        """
        mobile = citizen_mobile()
        if not mobile:
            return SIGN_IN_REQUIRED

        apps = get_apps_by_mobile(mobile)
        if not apps:
            return {
                "mobile_masked":  mask_mobile(mobile),
                "applications":   [],
                "next_step": {
                    "action": "ask_question",
                    "field":  "intent",
                    "prompt": "Aapke mobile number par koi application nahi mili. Kya aap abhi apply karna chahte hain?",
                    "options": ["Haan, apply karna hai", "Nahi"],
                },
            }

        summaries = [
            {
                "application_no":       a["application_no"],
                "status":               a["status"],
                "submitted_at":         a["submitted_at"],
                "decided_at":           a.get("decided_at"),
                "block":                a["block"],
                "village":              a["village"],
                "bank_account_masked":  mask_account(a.get("bank_account", "")),
            }
            for a in apps
        ]

        return {
            "mobile_masked": mask_mobile(mobile),
            "total":         len(summaries),
            "applications":  summaries,
            "status_guide": {
                "PENDING":         f"Samiksha ho rahi hai (officer ke paas hai, {config.SLA_DAYS} din mein decision aayega)",
                "APPROVED":        "Manzoor — pension disbursement shuru hoga",
                "DEEMED_APPROVED": f"{config.SLA_DAYS} din mein koi decision nahi aaya, isliye automatic manzoor ho gayi",
                "REJECTED":        "Asvikrit — reason ke liye get_application call karein",
                "WITHDRAWN":       "Aapne khud wapas li",
            },
            "next_step": {
                "action": "ask_question",
                "field":  "intent",
                "prompt": "Kisi ek application ki poori detail dekhni hai? Application number batayein.",
                "options": ["Haan, details chahiye", "Nahi"],
            },
        }

    @mcp.tool()
    def get_application(application_no: str) -> dict:
        """WHEN: citizen wants full details of one specific application.
        Shows rejection reason if REJECTED. Bank account is masked.

        Args:
            application_no: Application number like SSP26100001.
                            Get from my_applications() or ask the citizen.
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
                "next_step": NS.ASK_APP_NO_FOR_DETAIL,
            }

        app = get_app_by_no(application_no.strip())
        if not app or app.get("mobile") != mobile:
            return {
                "error": {
                    "code":    "NOT_FOUND",
                    "message": "Application not found or does not belong to this account.",
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action": "ask_question",
                    "field":  "application_no",
                    "prompt": "Yeh application number sahi nahi laga. Dobara check karein ya my_applications se list dekhein.",
                    "recovery": "ask_again",
                },
            }

        # Build citizen-safe view
        safe = {
            k: v for k, v in app.items()
            if k not in ("bank_account", "doc_path", "husband_employer", "mobile", "id")
        }
        safe["bank_account_masked"] = mask_account(app.get("bank_account", ""))
        safe["age_proof_type"] = (
            str(app.get("doc_path", ""))
            .replace(config.DECLARED_PREFIX, "")
            .replace("_", " ")
            .title()
            if str(app.get("doc_path", "")).startswith(config.DECLARED_PREFIX)
            else "Uploaded document"
        )

        # Surface rejection reason
        if app.get("status") == "REJECTED":
            safe["rejection_reason"] = get_decision_note(app.get("id") or 0)
            safe["next_step"] = {
                "action": "inform",
                "prompt": (
                    f"Aapki application {application_no} reject hui thi. Reason: "
                    f"{safe.get('rejection_reason') or 'officer ne reason nahi diya'}. "
                    "Kya aap dobara apply karna chahte hain?"
                ),
                "options": ["Haan, dobara apply karna hai", "Nahi"],
            }
        elif app.get("status") == "DEEMED_APPROVED":
            safe["next_step"] = {
                "action": "inform",
                "prompt": (
                    f"Aapki application {application_no} DEEMED_APPROVED hai — "
                    f"{config.SLA_DAYS} din mein officer ne koi decision nahi liya, "
                    "isliye Purvanchal Right to Public Services Act ke under automatic manzoor ho gayi. "
                    "Pension jald milegi."
                ),
            }
        else:
            safe["next_step"] = {
                "action": "inform",
                "prompt": (
                    f"Application {application_no} ka status hai: {app.get('status')}. "
                    "Kya kuch aur karna hai?"
                ),
            }

        return safe
