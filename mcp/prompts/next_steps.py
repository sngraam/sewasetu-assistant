"""
mcp/prompts/next_steps.py — All next_step constants.

next_step is a STRUCTURED object, not prose.  Small models parse objects
reliably; they miss things buried in paragraphs.

Shape:
{
    "action":          str   — what the model must do right now
    "prompt":          str   — exact text to say to the user (Hindi/Hinglish)
    "field":           str   — which field is being collected (optional)
    "remaining":       list  — fields still to collect (optional)
    "progress":        str   — "2 of 7 fields collected" (optional)
    "options":         list  — choices to present (optional)
    "recovery":        str   — what to do on error: ask_again | resend | stop | redirect
}

Actions:
    ask_question       — ask the user for one specific thing and wait
    confirm_and_submit — read back all details, ask yes/no, then call submit_application
    call_tool          — call a specific tool immediately
    inform             — tell the user something, no input needed
    redirect           — direct to counter / portal, close conversation
    stop               — eligibility failed, explain and end
"""
from __future__ import annotations
import config


# ── Identity ──────────────────────────────────────────────────────────────────

NOT_SIGNED_IN = {
    "action":  "inform",
    "prompt":  "Aapko Sewa Setu portal par sign in karna hoga. Kripya portal page kholein aur apna mobile number se sign in karein.",
    "recovery": "stop",
}

SESSION_ABOUT_TO_EXPIRE = {
    "action":  "inform",
    "prompt":  "Aapka session {minutes} minute mein khatam ho jayega. Jaldi se kaam pura kar lein.",
}


# ── Citizen Path A (Apply) ────────────────────────────────────────────────────

ASK_RESIDENCY = {
    "action":  "ask_question",
    "field":   "residency",
    "prompt":  "Kya aap Purvanchal ke sthayi niwasi hain? (Haan / Nahi)",
    "options": ["Haan", "Nahi"],
}

ASK_DOB = {
    "action":  "ask_question",
    "field":   "dob",
    "prompt":  "Aapki janam tithi kya hai? (DD/MM/YYYY format mein, jaise 15/03/1955)",
    "recovery": "ask_again",
}

ASK_BLOCK = {
    "action":  "ask_question",
    "field":   "block",
    "prompt":  f"Aap kis block mein rehte hain? Yeh blocks available hain: {', '.join(config.AGENT_BLOCKS)}",
    "options": config.AGENT_BLOCKS,
    "recovery": "ask_again",
}

ELIGIBLE_PROCEED = {
    "action":    "ask_question",
    "field":     "applicant_name",
    "prompt":    "Bahut accha! Aap eligible hain. Ab aapka poora naam batayein — bilkul waise jaisa age proof document mein likha hai.",
    "remaining": ["applicant_name", "gender", "marital_status", "village", "bank_account", "ifsc", "age_proof_type"],
    "progress":  "0 of 7 fields collected",
    "recovery":  "ask_again",
}

ASK_NAME = {
    "action":   "ask_question",
    "field":    "applicant_name",
    "prompt":   "Poora naam batayein — bilkul waise jaisa age proof document mein likha hai.",
    "progress": "1 of 7 fields collected",
    "recovery": "ask_again",
}

ASK_GENDER = {
    "action":   "ask_question",
    "field":    "gender",
    "prompt":   "Aapka gender kya hai?",
    "options":  ["Male", "Female", "Other"],
    "progress": "2 of 7 fields collected",
    "recovery": "ask_again",
}

ASK_MARITAL_STATUS = {
    "action":   "ask_question",
    "field":    "marital_status",
    "prompt":   "Aapki vaivahik sthiti (marital status) kya hai?",
    "options":  ["Married (Vivahit)", "Unmarried (Avivahit)", "Widowed (Vidhwa/Vidhur)"],
    "progress": "3 of 7 fields collected",
    "recovery": "ask_again",
}

ASK_HUSBAND_NAME = {
    "action":   "ask_question",
    "field":    "husband_name",
    "prompt":   "Apne late pati ka naam batayein.",
    "recovery": "ask_again",
}

ASK_VILLAGE = {
    "action":   "ask_question",
    "field":    "village",
    "prompt":   "Aapka gaon ya shahar ka naam kya hai?",
    "progress": "4 of 7 fields collected",
    "recovery": "ask_again",
}

ASK_BANK_ACCOUNT = {
    "action":   "ask_question",
    "field":    "bank_account",
    "prompt":   "Aapka bank account number kya hai? (9 se 18 digits, koi space ya dash nahi)",
    "progress": "5 of 7 fields collected",
    "recovery": "ask_again",
}

ASK_IFSC = {
    "action":   "ask_question",
    "field":    "ifsc",
    "prompt":   "Aapke bank branch ka IFSC code kya hai? (11 characters, jaise SBIN0003077)",
    "progress": "6 of 7 fields collected",
    "recovery": "ask_again",
}

ASK_AGE_PROOF = {
    "action":   "ask_question",
    "field":    "age_proof_type",
    "prompt":   "Aapke paas kaun sa age proof document hai?",
    "options":  list(config.VALID_AGE_PROOFS),
    "progress": "7 of 7 fields collected",
    "recovery": "ask_again",
}

CONFIRM_AND_SUBMIT = {
    "action": "confirm_and_submit",
    "prompt": "Sab details check kar lein. Kya sab sahi hai? Submit karein? (Haan / Nahi)",
    "options": ["Haan, submit karein", "Nahi, kuch badalna hai"],
}


def submitted_ok(app_no: str, proof: str) -> dict:
    return {
        "action": "inform",
        "prompt": (
            f"Badhai ho! Aapki application {app_no} submit ho gayi hai. "
            f"Application PENDING status mein hai. {config.SLA_DAYS} din mein decision aayega. "
            f"Status portal par track karein — password aapki janam tithi DDMMYYYY format mein hai. "
            f"Apna {proof} document taiyar rakhein — block officer verify karega."
        ),
    }


# ── Citizen Path B (Status) ───────────────────────────────────────────────────

ASK_APP_NO_FOR_DETAIL = {
    "action":   "ask_question",
    "field":    "application_no",
    "prompt":   "Kaunse application ki details chahiye? Application number batayein (jaise SSP26100001).",
    "recovery": "ask_again",
}

CONFIRM_WITHDRAW = {
    "action":  "ask_question",
    "field":   "withdraw_confirm",
    "prompt":  "Kya aap pakka apni application wapas lena chahte hain? Yeh action undo nahi ho sakta. (Haan / Nahi)",
    "options": ["Haan, wapas lo", "Nahi"],
}


def withdrawn_ok(app_no: str) -> dict:
    return {
        "action": "inform",
        "prompt": (
            f"Application {app_no} wapas le li gayi hai. "
            "Agar dobara apply karna ho to main madad kar sakta hoon."
        ),
    }


# ── Ineligible / errors ───────────────────────────────────────────────────────

def ineligible_age(age: int) -> dict:
    return {
        "action":   "stop",
        "prompt":   f"Maafi chahta hoon — aapki umar {age} saal hai. Is yojana ke liye kam se kam {config.MIN_AGE} saal ki umar chahiye.",
        "recovery": "stop",
    }


def ineligible_block(block: str) -> dict:
    return {
        "action":   "redirect",
        "prompt":   (
            f"'{block}' block abhi AI channel mein nahi hai. "
            f"Kripya apne nearest block office counter par jaakar apply karein. "
            f"AI channel ke pilot blocks hain: {', '.join(config.AGENT_BLOCKS)}."
        ),
        "recovery": "redirect",
    }


SCHEME_CLOSED = {
    "action":   "stop",
    "prompt":   "Maafi chahta hoon — yojana ki application window 31 October 2026 ko band ho gayi. Ab apply nahi ho sakta.",
    "recovery": "stop",
}

DUPLICATE_ACTIVE = {
    "action":   "call_tool",
    "tool":     "my_applications",
    "prompt":   "Aapke mobile number par pehle se ek active application hai. Pehle uska status dekhte hain.",
}


# ── Officer next steps ────────────────────────────────────────────────────────

OFFICER_START = {
    "action": "call_tool",
    "tool":   "queue_summary",
    "prompt": "Queue summary dekh rahe hain...",
}

OFFICER_VIEW_LIST = {
    "action": "inform",
    "prompt": "List mein se ek application chunein aur uska application number batayein get_dossier ke liye.",
}


def officer_dossier_warnings(warnings: list[str]) -> dict:
    if not warnings:
        return {
            "action": "inform",
            "prompt": "Koi warning nahi. Application decide karne ke liye decide_application call karein.",
        }
    w_text = "; ".join(warnings)
    return {
        "action": "inform",
        "prompt": f"WARNING ({len(warnings)} flag(s)): {w_text}. Review carefully before deciding.",
    }


def officer_decided(app_no: str, status: str) -> dict:
    return {
        "action": "inform",
        "prompt": (
            f"Application {app_no} {status.lower()} kar di gayi. "
            "Aapka naam audit log mein record ho gaya. "
            "Next application ke liye list_pending call karein."
        ),
    }
