"""
parasite_ai/safety/content_scanner.py - Synchronous Zero-VRAM Content & Secret Scanner.

Screens persisted SKILL.md artifacts, farmed plans, and deferred co-author traces
against prompt-injection markers (hard reject) and common secret/credential tokens
(in-place redaction to ``[REDACTED_SECRET]``).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, Pattern, Tuple

REDACTED_SECRET_MARKER = "[REDACTED_SECRET]"

_INJECTION_PATTERNS: Tuple[Tuple[str, Pattern[str]], ...] = (
    ("<|im_start|>", re.compile(r"<\|im_start\|>", re.IGNORECASE)),
    ("<|endoftext|>", re.compile(r"<\|endoftext\|>", re.IGNORECASE)),
    ("[system]", re.compile(r"\[system\]", re.IGNORECASE)),
    (
        "ignore previous/prior instructions",
        re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b", re.IGNORECASE),
    ),
)

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----(?:[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----|[^\r\n\"]*)"
)
_SK_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_AIZA_KEY_RE = re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b")
_GHP_KEY_RE = re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")
_BEARER_RE = re.compile(
    rf"\bBearer\s+(?!{re.escape(REDACTED_SECRET_MARKER)})[A-Za-z0-9._~+/-]{{16,}}\b",
    re.IGNORECASE,
)
_CRED_ASSIGN_RE = re.compile(
    rf"(?i)\b(password|passwd|secret|api_key|access_token)\s*[:=]\s*(?!{re.escape(REDACTED_SECRET_MARKER)})([^\s,;'\")}}\]]+)"
)


@dataclass(frozen=True)
class ScanResult:
    """Outcome of synchronous prompt-injection & secret scanning."""

    allowed: bool
    text: str
    reason: Optional[str] = None
    redacted_count: int = 0


def sanitize_or_reject(text: str) -> ScanResult:
    """
    Screens ``text`` for prompt-injection markers (hard reject) and secrets (redact).

    Returns a ``ScanResult`` with ``allowed=False`` if any injection marker is found,
    otherwise ``allowed=True`` with secrets replaced by ``[REDACTED_SECRET]``.
    """
    if not text:
        return ScanResult(allowed=True, text="", reason=None, redacted_count=0)
    if not isinstance(text, str):
        return ScanResult(allowed=False, text="", reason="Content must be a string.", redacted_count=0)

    for label, pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return ScanResult(
                allowed=False,
                text="",
                reason=f"Blocked prompt-injection marker: {label}",
                redacted_count=0,
            )

    cleaned = text
    redacted_count = 0

    for pat, repl in (
        (_PRIVATE_KEY_RE, REDACTED_SECRET_MARKER),
        (_SK_KEY_RE, REDACTED_SECRET_MARKER),
        (_AIZA_KEY_RE, REDACTED_SECRET_MARKER),
        (_GHP_KEY_RE, REDACTED_SECRET_MARKER),
        (_BEARER_RE, f"Bearer {REDACTED_SECRET_MARKER}"),
        (_CRED_ASSIGN_RE, rf"\1={REDACTED_SECRET_MARKER}"),
    ):
        cleaned, count = pat.subn(repl, cleaned)
        redacted_count += count

    reason = (
        f"Redacted {redacted_count} secret token(s)."
        if redacted_count > 0
        else None
    )
    return ScanResult(
        allowed=True,
        text=cleaned,
        reason=reason,
        redacted_count=redacted_count,
    )


class ContentScanner:
    """Stateless synchronous CPU content & secret scanner."""

    def scan(self, text: str) -> ScanResult:
        """Scans ``text`` and returns ``ScanResult``."""
        return sanitize_or_reject(text)

    def sanitize_or_reject(self, text: str) -> ScanResult:
        """Alias for ``scan(text)``."""
        return sanitize_or_reject(text)
