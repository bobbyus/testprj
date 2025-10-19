from __future__ import annotations

import re
from typing import Dict, Optional, Tuple
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser

INLINE_HEADER_RE = re.compile(r"^(From|To|Subject|Date|Message-Id):\s*(.*)$", re.IGNORECASE)
FORWARDED_MARKERS = [
    "---------- Forwarded message ---------",
    "Begin forwarded message:",
    "Forwarded message:",
]


def find_rfc822_message(msg: EmailMessage) -> Optional[EmailMessage]:
    for part in msg.walk():
        if part.get_content_type() == "message/rfc822":
            payload = part.get_payload()
            # The payload may be a list with a single EmailMessage or bytes
            if isinstance(payload, list) and payload and isinstance(payload[0], EmailMessage):
                return payload[0]
            # Some implementations return bytes
            raw = part.get_payload(decode=True)
            if raw:
                try:
                    inner = BytesParser(policy=policy.default).parsebytes(raw)
                    return inner
                except Exception:
                    pass
    return None


def parse_inline_forwarded_headers(text: str) -> Tuple[Dict[str, str], Optional[Tuple[int, int]]]:
    lines = text.splitlines()
    start_idx = None
    # Try to locate marker or first From:
    for i, line in enumerate(lines):
        if any(m.lower() in line.lower() for m in FORWARDED_MARKERS):
            # Next non-empty line that looks like a header
            for j in range(i + 1, min(i + 20, len(lines))):
                if INLINE_HEADER_RE.match(lines[j]):
                    start_idx = j
                    break
            if start_idx is not None:
                break
    if start_idx is None:
        # Find first header-like line near top
        for i, line in enumerate(lines[:50]):
            if INLINE_HEADER_RE.match(line):
                start_idx = i
                break
    if start_idx is None:
        return {}, None

    headers: Dict[str, str] = {}
    idx = start_idx
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            # blank line ends header block
            end_idx = idx
            return headers, (start_idx, end_idx)
        m = INLINE_HEADER_RE.match(line)
        if not m:
            # If folded header continuation (starts with space or tab)
            if line.startswith(" ") or line.startswith("\t"):
                # append to last header
                if headers:
                    last_key = list(headers.keys())[-1]
                    headers[last_key] = headers[last_key] + " " + line.strip()
                idx += 1
                continue
            else:
                break
        key = m.group(1).title()
        value = m.group(2).strip()
        headers[key] = value
        idx += 1
    # reached end without blank line
    return headers, (start_idx, idx)


def strip_header_block_from_text(text: str, block_range: Optional[Tuple[int, int]]) -> str:
    if not block_range:
        return text
    start, end = block_range
    lines = text.splitlines()
    # Remove the header block and any preceding forwarded marker line
    remove_from = start
    # Remove marker line immediately before if present
    if remove_from > 0 and any(
        m.lower() in lines[remove_from - 1].lower() for m in FORWARDED_MARKERS
    ):
        remove_from = remove_from - 1
    new_lines = lines[:remove_from] + lines[end + 1 :]
    return "\n".join(new_lines).lstrip("\n")


def get_original_message_and_headers(
    msg: EmailMessage,
) -> Tuple[EmailMessage, Dict[str, str], Optional[str], str]:
    """
    Returns a tuple of:
    - original EmailMessage (prioritizing embedded message/rfc822)
    - parsed inline forwarded headers if any
    - cleaned text body if inline headers were used (body with header block removed)
    - method used: "rfc822" | "inline" | "top"
    """
    # 1) Embedded message
    inner = find_rfc822_message(msg)
    if inner is not None:
        return inner, {}, None, "rfc822"

    # 2) Inline forwarded header block
    # Need a text to scan; try extracting from the outer message
    from .body_extractor import extract_text

    outer_text = extract_text(msg)
    headers, block_range = parse_inline_forwarded_headers(outer_text)
    if headers:
        cleaned = strip_header_block_from_text(outer_text, block_range)
        return msg, headers, cleaned, "inline"

    # 3) Fallback to top-level headers and attempt heuristics from body
    return msg, {}, None, "top"
