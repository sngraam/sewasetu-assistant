"""
Sewa Setu Eval Personas — 8 invented citizens and 2 officers used to exercise
the MCP servers and evaluate correctness.

Each persona has:
  name          — full name
  age           — current age
  mobile        — 10-digit number (unique, not in seed data)
  role          — "citizen" or "officer"
  language      — how they communicate
  scenario      — what they want in this conversation
  eligibility   — ELIGIBLE / INELIGIBLE / OFFICER (with reason if ineligible)
  expected_db   — what must be true in the DB after the conversation
  pass_criteria — how we verify the conversation succeeded
  result        — PASS / FAIL / PENDING (filled in after the eval run)
  notes         — what happened, what we learned
"""

PERSONAS = [
    {
        "id": "P01",
        "name": "Ramwati Devi",
        "age": 71,
        "mobile": "9100010001",
        "dob": "15/03/1955",
        "role": "citizen",
        "language": "Hindi",
        "scenario": (
            "First-time applicant. Widow. Lives in Sonari (pilot block). "
            "Has a Voter ID. Wants to apply for the pension for herself. "
            "Her son is helping her type on a shared kiosk phone."
        ),
        "eligibility": "ELIGIBLE",
        "block": "Sonari",
        "gender": "Female",
        "marital_status": "Widowed",
        "husband_name": "Late Ramswaroop",
        "village": "Kathoni",
        "bank_account": "3876903950095",
        "ifsc": "SBIN0003077",
        "age_proof_type": "Voter ID",
        "expected_db": (
            "A new PENDING application exists for mobile 9100010001. "
            "doc_path starts with declared://. "
            "portal_users row created with password = DOB as DDMMYYYY."
        ),
        "pass_criteria": [
            "Application number (SSP*) returned to citizen",
            "Row in applications table with status=PENDING",
            "doc_path = declared://voter_id",
            "portal_users row for 9100010001 exists",
        ],
        "result": "PENDING",
        "notes": "",
    },
    {
        "id": "P02",
        "name": "Mohan Lal Yadav",
        "age": 64,
        "mobile": "9100010002",
        "dob": "07/07/1962",
        "role": "citizen",
        "language": "Hindi-Bhojpuri mix",
        "scenario": (
            "First-time applicant. Married. Lives in Rajapara (pilot block). "
            "Has a birth certificate. Speaks slowly, types carefully. "
            "Needs to be told what IFSC means."
        ),
        "eligibility": "ELIGIBLE",
        "block": "Rajapara",
        "gender": "Male",
        "marital_status": "Married",
        "husband_name": "",
        "village": "Teliagaon",
        "bank_account": "129068125527",
        "ifsc": "UTBI0PUR2819",
        "age_proof_type": "Birth certificate",
        "expected_db": (
            "A new PENDING application exists for mobile 9100010002. "
            "doc_path = declared://birth_certificate."
        ),
        "pass_criteria": [
            "Application number returned",
            "status=PENDING in DB",
            "doc_path = declared://birth_certificate",
        ],
        "result": "PENDING",
        "notes": "",
    },
    {
        "id": "P03",
        "name": "Sarojini Das",
        "age": 68,
        "mobile": "9100010003",
        "dob": "22/11/1957",
        "role": "citizen",
        "language": "Assamese-Hindi mix",
        "scenario": (
            "Already has a PENDING application (pre-seeded in DB before eval). "
            "Wants to check her status — worried it has been too long. "
            "Does NOT want to withdraw or re-apply."
        ),
        "eligibility": "ELIGIBLE",
        "block": "Dhemaji Pathar",
        "pre_seed_status": "PENDING",
        "expected_db": (
            "The PENDING application for 9100010003 remains PENDING. "
            "No withdrawal, no new application."
        ),
        "pass_criteria": [
            "my_applications returns 1 application with status PENDING",
            "No new application created in DB",
            "No withdrawal recorded in audit_log",
        ],
        "result": "PENDING",
        "notes": "",
    },
    {
        "id": "P04",
        "name": "Abdul Karim",
        "age": 62,
        "mobile": "9100010004",
        "dob": "01/04/1964",
        "role": "citizen",
        "language": "Hinglish",
        "scenario": (
            "Had a REJECTED application (pre-seeded). Wants to withdraw it and "
            "re-apply with a corrected bank account. "
            "Tests that REJECTED → withdraw is not allowed; "
            "instead the system should let them apply afresh directly "
            "(REJECTED does not block a new application)."
        ),
        "eligibility": "ELIGIBLE",
        "block": "Borgaon",
        "pre_seed_status": "REJECTED",
        "expected_db": (
            "A new PENDING application for 9100010004 created "
            "(REJECTED does not count as active, so no withdrawal needed)."
        ),
        "pass_criteria": [
            "New PENDING application created",
            "Old REJECTED application still present unchanged",
            "REJECTED application cannot be withdrawn (error returned)",
        ],
        "result": "PENDING",
        "notes": "",
    },
    {
        "id": "P05",
        "name": "Geeta Devi",
        "age": 61,
        "mobile": "9100010005",
        "dob": "11/06/1965",
        "role": "citizen",
        "language": "Hindi",
        "scenario": (
            "Lives in Namti — a valid block but NOT in the pilot scope for the AI channel. "
            "Tries to apply via the assistant. "
            "Must be redirected to the counter politely."
        ),
        "eligibility": "INELIGIBLE",
        "ineligibility_reason": "Block 'Namti' is not in the AI pilot scope",
        "block": "Namti",
        "expected_db": "No application created in DB.",
        "pass_criteria": [
            "check_eligibility returns eligible=False",
            "Reason mentions pilot blocks or counter",
            "No application row created for 9100010005",
        ],
        "result": "PENDING",
        "notes": "",
    },
    {
        "id": "P06",
        "name": "Ramesh Kumar Yadav",
        "age": 58,
        "mobile": "9100010006",
        "dob": "05/09/1968",
        "role": "citizen",
        "language": "Hindi",
        "scenario": (
            "Too young — 58 years old, does not meet the 60-year minimum. "
            "Tries to apply. Must be turned away kindly."
        ),
        "eligibility": "INELIGIBLE",
        "ineligibility_reason": "Age 58 < minimum 60",
        "block": "Sonari",
        "expected_db": "No application created in DB.",
        "pass_criteria": [
            "check_eligibility returns eligible=False",
            "Reason mentions minimum age",
            "No application row created for 9100010006",
        ],
        "result": "PENDING",
        "notes": "",
    },
    {
        "id": "P07",
        "name": "Arun Kumar (Officer)",
        "age": 38,
        "mobile": None,
        "role": "officer",
        "language": "English",
        "scenario": (
            "Block officer. Wants to see the pending queue, open the dossier of "
            "a declared-only application (P01's application), confirm he has "
            "seen the physical Voter ID, and approve it."
        ),
        "expected_db": (
            "P01's application is APPROVED. "
            "audit_log has an APPROVED entry with decided_by = officer username. "
            "decided_at is set."
        ),
        "pass_criteria": [
            "queue_summary returns non-empty by_status",
            "list_pending returns P01's application",
            "get_dossier shows declared_only=True and DECLARED ONLY in age_proof_note",
            "decide_application with confirmed_original_seen=True → APPROVED",
            "DB shows status=APPROVED, decided_by=officer_name",
        ],
        "result": "PENDING",
        "notes": "",
    },
    {
        "id": "P08",
        "name": "Priya Singh (Officer)",
        "age": 34,
        "mobile": None,
        "role": "officer",
        "language": "English",
        "scenario": (
            "Block officer. Rejects an application (P02's application) because "
            "the bank account could not be verified. Reason must be recorded."
        ),
        "expected_db": (
            "P02's application is REJECTED. "
            "audit_log has a REJECTED entry with the reason note. "
            "decided_by = officer username."
        ),
        "pass_criteria": [
            "decide_application REJECT without reason → error returned",
            "decide_application REJECT with reason → REJECTED in DB",
            "audit_log note matches the rejection reason",
            "decided_by matches the officer's sign-in name",
        ],
        "result": "PENDING",
        "notes": "",
    },
]
