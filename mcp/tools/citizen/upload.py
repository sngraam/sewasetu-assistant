"""
tools/citizen/upload.py — stage_document tool.

The agent cannot upload files itself but the citizen may point it to a file
that already exists on the local machine (kiosk, shared PC, etc.).
This tool copies the file to a secure temp area and returns a temp_ref
that submit_application uses to commit it permanently once confirmed.

TWO-STAGE FLOW
    1. stage_document(file_path, age_proof_type)
       → validates extension + size → copies to temp → returns temp_ref
    2. submit_application(..., temp_ref=...)
       → on success, moves temp to /var/sewasetu/uploads/{app_no}/age_proof.ext
"""
import config
from auth import citizen_mobile, SIGN_IN_REQUIRED
from middleware.uploads import stage_document as _stage, get_staged_info


def register(mcp):

    @mcp.tool()
    def stage_document(file_path: str, age_proof_type: str) -> dict:
        """WHEN: citizen provides a local file path for their age proof document.
        Validates and stages the file. Returns a temp_ref to pass to submit_application.
        Call this BEFORE submit_application when the citizen has a physical file available.
        If no file is available, submit_application still works using a declaration only.

        Args:
            file_path:      Absolute path to the document on the local machine.
                            Examples: /home/user/voter_id.pdf
                                      /home/user/Documents/birth_cert.jpg
                                      /tmp/school_cert.png
                            Accepted formats: .pdf .jpg .jpeg .png (max 5 MB)

            age_proof_type: Which document this is.
                            One of: Voter ID, Birth certificate, School leaving certificate.
        """
        mobile = citizen_mobile()
        if not mobile:
            return SIGN_IN_REQUIRED

        # Validate age_proof_type first — before touching the filesystem
        proof = (age_proof_type or "").strip()
        proof_match = next(
            (p for p in config.VALID_AGE_PROOFS if p.lower() == proof.lower()), None
        )
        if not proof_match:
            return {
                "error": {
                    "code":     "INVALID_AGE_PROOF_TYPE",
                    "message":  f"age_proof_type must be one of: {', '.join(config.VALID_AGE_PROOFS)}.",
                    "recovery": "ask_again",
                },
                "next_step": {
                    "action":  "ask_question",
                    "field":   "age_proof_type",
                    "prompt":  "Kaun sa document hai? Voter ID, Birth certificate, ya School leaving certificate?",
                    "options": list(config.VALID_AGE_PROOFS),
                    "recovery": "ask_again",
                },
            }

        result = _stage(mobile, file_path, proof_match)

        # On success, add helpful context about what to do next
        if result.get("staged"):
            result["instruction"] = (
                "Pass temp_ref to submit_application when submitting. "
                "The file will be permanently stored under the application number once confirmed."
            )

        return result

    @mcp.tool()
    def check_staged_document() -> dict:
        """WHEN: checking if a document is already staged before submitting.
        Shows what file is currently held in the staging area for this citizen.
        Useful at the confirmation step — tells the citizen which file will be submitted.
        Takes no arguments.
        """
        mobile = citizen_mobile()
        if not mobile:
            return SIGN_IN_REQUIRED

        import re
        safe_mobile = re.sub(r"[^0-9]", "", mobile)[:15]

        from pathlib import Path
        import config as cfg
        temp_dir = Path(cfg.TEMP_ROOT) / safe_mobile
        if not temp_dir.exists():
            return {
                "has_staged_document": False,
                "next_step": {
                    "action": "inform",
                    "prompt": (
                        "Koi document stage nahi hua hai. Agar aapke paas file available hai, "
                        "stage_document(file_path, age_proof_type) call karein. "
                        "Bina file ke bhi submit kar sakte hain — officer verification karega."
                    ),
                },
            }

        files = [f for f in temp_dir.iterdir() if f.is_file()]
        if not files:
            return {
                "has_staged_document": False,
                "next_step": {
                    "action": "inform",
                    "prompt": "Staging folder khaali hai. stage_document se pehle file upload karein.",
                },
            }

        f = files[0]  # only one file per mobile at a time
        import time as _t
        stat = f.stat()
        return {
            "has_staged_document": True,
            "staged_file": {
                "filename":  f.name,
                "size_kb":   round(stat.st_size / 1024, 1),
                "staged_at": _t.strftime("%Y-%m-%d %H:%M", _t.localtime(stat.st_mtime)),
            },
            "temp_ref": f"{safe_mobile}/{f.name}",
            "next_step": {
                "action": "inform",
                "prompt": (
                    f"File '{f.name}' ({round(stat.st_size/1024, 1)} KB) staged hai. "
                    "Submit karte waqt temp_ref use hoga."
                ),
            },
        }
