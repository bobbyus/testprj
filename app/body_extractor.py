from __future__ import annotations

from email.message import EmailMessage
from typing import Optional
from bs4 import BeautifulSoup


def _is_attachment(part: EmailMessage) -> bool:
    disp = part.get("Content-Disposition", "").lower()
    return disp.startswith("attachment")


def _get_charset(part: EmailMessage) -> Optional[str]:
    charset = part.get_content_charset()
    return charset


def _decode_payload(part: EmailMessage) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        # Could be a str already
        try:
            payload = part.get_payload()
            if isinstance(payload, str):
                return payload
            return ""
        except Exception:
            return ""
    charset = _get_charset(part) or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except Exception:
        try:
            return payload.decode("utf-8", errors="replace")
        except Exception:
            return payload.decode(errors="replace")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Preserve reasonable whitespace
    text = soup.get_text(separator="\n", strip=False)
    return text


def extract_text(msg: EmailMessage) -> str:
    # Prefer text/plain
    if msg.is_multipart():
        # Find first suitable text/plain part that is not an attachment
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if _is_attachment(part):
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain":
                return _decode_payload(part)
        # Fallback to first text/html part
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if _is_attachment(part):
                continue
            ctype = part.get_content_type()
            if ctype == "text/html":
                html = _decode_payload(part)
                return html_to_text(html)
        # Last resort: decode any text/*
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if _is_attachment(part):
                continue
            if part.get_content_maintype() == "text":
                return _decode_payload(part)
        return ""
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            return _decode_payload(msg)
        elif ctype == "text/html":
            html = _decode_payload(msg)
            return html_to_text(html)
        elif msg.get_content_maintype() == "text":
            return _decode_payload(msg)
        else:
            return ""
