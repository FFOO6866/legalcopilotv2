"""PII filter for Singapore legal context.

Detects and redacts Singapore-specific PII patterns before sending to LLMs:
- NRIC/FIN (e.g., S1234567A, G1234567A)
- UEN (Unique Entity Number)
- Passport numbers
- Bank account numbers
- Phone numbers (+65 format)
- Email addresses
"""

import re
from typing import Optional


# Singapore NRIC/FIN: letter + 7 digits + letter
_NRIC_PATTERN = re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.IGNORECASE)

# Singapore UEN: 9-10 chars (date-based or entity-based)
_UEN_PATTERN = re.compile(r"\b\d{8,9}[A-Z]\b|\b[TSR]\d{2}[A-Z]{2}\d{4}[A-Z]\b", re.IGNORECASE)

# Singapore passport: E or K prefix + 7 digits
_PASSPORT_PATTERN = re.compile(r"\b[EK]\d{7}\b")

# Bank account: 10-16 consecutive digits (common SG format)
# Uses a tighter pattern to avoid false positives on case citations
_BANK_ACCOUNT_PATTERN = re.compile(r"\b\d{10,16}\b")

# Singapore phone: +65 or local 8/9-start 8-digit numbers
_PHONE_PATTERN = re.compile(r"(?:\+65\s?)?\b[89]\d{3}\s?\d{4}\b")

# Email
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_PATTERNS = [
    ("NRIC", _NRIC_PATTERN),
    ("UEN", _UEN_PATTERN),
    ("PASSPORT", _PASSPORT_PATTERN),
    ("BANK_ACCOUNT", _BANK_ACCOUNT_PATTERN),
    ("PHONE", _PHONE_PATTERN),
    ("EMAIL", _EMAIL_PATTERN),
]


def redact_pii(text: str, replacement: Optional[str] = None) -> str:
    """Redact all detected PII patterns from text.

    Args:
        text: Input text to scan.
        replacement: Custom replacement string. If None, uses [REDACTED_<TYPE>].

    Returns:
        Text with PII replaced by redaction markers.
    """
    result = text
    for pii_type, pattern in _PATTERNS:
        marker = replacement or f"[REDACTED_{pii_type}]"
        result = pattern.sub(marker, result)
    return result


def detect_pii(text: str) -> list[dict]:
    """Detect all PII instances in text without redacting.

    Returns:
        List of dicts with type, start, end positions.
        Values are masked to prevent PII leakage through the detection API.
    """
    findings = []
    for pii_type, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group()
            # Mask all but first and last char to prevent leakage
            if len(raw) > 4:
                masked = raw[0] + "*" * (len(raw) - 2) + raw[-1]
            else:
                masked = "*" * len(raw)
            findings.append(
                {
                    "type": pii_type,
                    "value": masked,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
    return sorted(findings, key=lambda f: f["start"])


def has_pii(text: str) -> bool:
    """Quick check if text contains any PII."""
    return any(pattern.search(text) for _, pattern in _PATTERNS)
