"""tools/citizen/scheme_info.py — Scheme eligibility and rules."""
import config


def register(mcp):
    @mcp.tool()
    def get_scheme_info() -> dict:
        """WHEN: citizen asks what this scheme is, who is eligible, or what documents are needed.
        Returns all scheme facts. Takes no arguments.
        """
        return {
            "scheme":     "Old Age Pension Scheme — Government of Purvanchal",
            "department": "Department of Social Welfare",
            "pension_amount": "Rs.250 per month (credited via Direct Benefit Transfer)",
            "eligibility": {
                "minimum_age":       config.MIN_AGE,
                "residency":         "Permanent resident of Purvanchal",
                "income_limit":      "None",
                "existing_pension":  "Cannot hold another active government pension",
            },
            "required_documents": [
                f"Age proof: {', '.join(config.VALID_AGE_PROOFS)}",
                "Bank account number (9–18 digits)",
                "IFSC code of bank branch",
            ],
            "valid_blocks":        config.BLOCKS,
            "agent_pilot_blocks":  config.AGENT_BLOCKS,
            "agent_note":          (
                f"AI channel covers only: {', '.join(config.AGENT_BLOCKS)}. "
                "Citizens in other blocks must apply at the counter."
            ),
            "gender_options":       ["Male", "Female", "Other"],
            "marital_status_options": ["Married", "Unmarried", "Widowed"],
            "application_window":  "Closes 31 October 2026 at midnight",
            "sla_days":            config.SLA_DAYS,
            "auto_approval_note":  (
                f"If the officer takes no decision within {config.SLA_DAYS} days, "
                "the application is automatically approved (DEEMED_APPROVED) under the "
                "Purvanchal Right to Public Services Act."
            ),
            "status_portal_password": "Your date of birth as DDMMYYYY (e.g. 05071948)",
            "next_step": {
                "action":  "ask_question",
                "field":   "intent",
                "prompt":  "Kya aap naya pension apply karna chahte hain ya purani application check karni hai?",
                "options": ["Naya apply karna hai", "Purani application check karni hai"],
            },
        }
