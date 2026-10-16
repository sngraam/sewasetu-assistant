"""mcp/middleware/masking.py — PII masking utilities."""


def mask_account(account: str) -> str:
    """Show only last 4 digits: '123456789012' → '********9012'."""
    s = str(account or "")
    if not s:
        return ""
    return ("*" * (len(s) - 4) + s[-4:]) if len(s) > 4 else s


def mask_mobile(mobile: str) -> str:
    """Show first 2 and last 4: '9876543210' → '98****3210'."""
    s = str(mobile or "")
    if not s or len(s) < 6:
        return s
    return s[:2] + "*" * (len(s) - 6) + s[-4:]
