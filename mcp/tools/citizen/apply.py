"""tools/citizen/apply.py — Submit a new pension application."""
import logging

import config
from auth import citizen_mobile, SIGN_IN_REQUIRED
from db.citizen import has_active_application
from domain.validation import validate_application
from domain.application import create_application
from prompts import next_steps as NS

log = logging.getLogger("sewasetu.tools.citizen.apply")


def register(mcp):
    @mcp.tool()
    def submit_application(
        applicant_name:  str,
        dob:             str,
        gender:          str,
        marital_status:  str,
        village:         str,
        block:           str,
        bank_account:    str,
        ifsc:            str,
        age_proof_type:  str,
        husband_name:    str = "",
    ) -> dict:
        """WHEN: citizen has confirmed ALL details are correct and said "haan" / "yes".
        Creates the application. Do NOT call this until you have an explicit confirmation.
        Mobile is taken from the sign-in token — do NOT ask for it.

        Args:
            applicant_name:  Full name as on age proof document. Example: Ramwati Devi.
            dob:             Date of birth as DD/MM/YYYY. Example: 12/03/1955. Must be 60+.
            gender:          One of: Male, Female, Other.
            marital_status:  One of: Married, Unmarried, Widowed.
            village:         Village or town name. Example: Kathoni.
            block:           One of the 6 valid blocks. Must be a pilot block for AI channel.
            bank_account:    Bank account number, 9–18 digits, no spaces or dashes.
            ifsc:            IFSC code, 11 characters. Example: SBIN0003077.
            age_proof_type:  One of: Voter ID, Birth certificate, School leaving certificate.
            husband_name:    Late husband's name. ONLY if marital_status is Widowed.
        """
        mobile = citizen_mobile()
        if not mobile:
            return SIGN_IN_REQUIRED

        # ── Pilot block guard ─────────────────────────────────────────────────
        block_clean = (block or "").strip()
        if block_clean and block_clean not in config.AGENT_BLOCKS:
            return {
                "error": {
                    "code":    "BLOCK_NOT_IN_PILOT",
                    "message": f"Block '{block_clean}' is not in the AI pilot scope.",
                    "recovery": "redirect",
                },
                "next_step": NS.ineligible_block(block_clean),
            }

        # ── Duplicate guard ───────────────────────────────────────────────────
        active = has_active_application(mobile)
        if active:
            return {
                "error": {
                    "code":           "DUPLICATE_ACTIVE",
                    "message":        f"Active application {active['application_no']} ({active['status']}) already exists.",
                    "application_no": active["application_no"],
                    "status":         active["status"],
                    "recovery":       "call_tool",
                },
                "next_step": NS.DUPLICATE_ACTIVE,
            }

        # ── Normalise gender / marital status ─────────────────────────────────
        gender_clean = (gender or "").strip().capitalize()
        if gender_clean not in ("Male", "Female", "Other"):
            return {
                "error": {
                    "code":         "INVALID_FIELD",
                    "field":        "gender",
                    "message":      "Gender must be Male, Female, or Other.",
                    "recovery":     "ask_again",
                    "retry_prompt": "Aapka gender kya hai? Male, Female, ya Other?",
                },
                "next_step": NS.ASK_GENDER,
            }

        ms_clean = (marital_status or "").strip().capitalize()
        if ms_clean not in ("Married", "Unmarried", "Widowed"):
            return {
                "error": {
                    "code":         "INVALID_FIELD",
                    "field":        "marital_status",
                    "message":      "Marital status must be Married, Unmarried, or Widowed.",
                    "recovery":     "ask_again",
                    "retry_prompt": "Aapki vaivahik sthiti kya hai?",
                },
                "next_step": NS.ASK_MARITAL_STATUS,
            }

        # ── Age proof — declaration marker ────────────────────────────────────
        proof = (age_proof_type or "").strip()
        proof_match = next(
            (p for p in config.VALID_AGE_PROOFS if p.lower() == proof.lower()), None
        )
        if not proof_match:
            return {
                "error": {
                    "code":     "INVALID_FIELD",
                    "field":    "age_proof_type",
                    "message":  f"Age proof must be one of: {', '.join(config.VALID_AGE_PROOFS)}.",
                    "recovery": "ask_again",
                },
                "next_step": NS.ASK_AGE_PROOF,
            }

        doc_path = config.DECLARED_PREFIX + proof_match.lower().replace(" ", "_")

        data = {
            "applicant_name": applicant_name,
            "dob":            dob,
            "gender":         gender_clean,
            "marital_status": ms_clean,
            "husband_name":   husband_name if ms_clean == "Widowed" else "",
            "village":        village,
            "block":          block_clean,
            "bank_account":   bank_account,
            "ifsc":           ifsc,
        }

        errors, cleaned = validate_application(data, doc_path)
        if errors:
            # Find the first invalid field so the model asks exactly that question
            first_error = errors[0]
            return {
                "error": {
                    "code":     "VALIDATION_FAILED",
                    "message":  first_error,
                    "all":      errors,
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action": "ask_question",
                    "prompt": f"Ek galti mili: {first_error} Kripya sahi value batayein.",
                    "recovery": "ask_again",
                },
            }

        try:
            new_id, app_no = create_application(mobile, cleaned)
        except Exception:
            log.exception("DB error creating application for mobile=%s", mobile)
            return {
                "error": {
                    "code":     "SERVER_ERROR",
                    "message":  "A database error occurred.",
                    "recovery": "stop",
                },
                "next_step": {
                    "action": "inform",
                    "prompt": "Maafi chahta hoon — ek technical problem aayi. Thodi der baad dobara try karein.",
                },
            }

        return {
            "success":           True,
            "application_no":    app_no,
            "application_id":    new_id,
            "status":            "PENDING",
            "age_proof_declared": proof_match,
            "next_step":         NS.submitted_ok(app_no, proof_match),
        }
