from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional
from email.utils import parsedate_to_datetime

from .models import EmailOutput

EMAILS_DIR = os.path.join(os.getcwd(), "emails")
SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_emails_dir() -> str:
    os.makedirs(EMAILS_DIR, exist_ok=True)
    return EMAILS_DIR


def sanitize_message_id(message_id: Optional[str]) -> str:
    if not message_id:
        return ""
    # Strip angle brackets and sanitize
    mid = message_id.strip().strip("<>")
    mid = SANITIZE_RE.sub("", mid)
    return mid or ""


def parse_date_to_utc(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    # Try RFC 3339 / ISO 8601
    s = date_str.strip()
    try:
        # Support trailing Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # Try email date
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def format_timestamp(dt: Optional[datetime]) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def stable_hash(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        if p:
            h.update(p.encode("utf-8", errors="ignore"))
    return h.hexdigest()[:16]


def pick_filename(ts: str, message_id: Optional[str]) -> str:
    ensure_emails_dir()
    sanitized = sanitize_message_id(message_id)
    if not sanitized:
        sanitized = stable_hash(ts)
    base = f"{ts}_{sanitized}.json"
    path = os.path.join(EMAILS_DIR, base)
    if not os.path.exists(path):
        return path
    # de-dup with suffix
    i = 1
    while True:
        alt = os.path.join(EMAILS_DIR, f"{ts}_{sanitized}-{i}.json")
        if not os.path.exists(alt):
            return alt
        i += 1


def write_email_json(
    output: EmailOutput,
    fallback_header_date: Optional[str] = None,
) -> str:
    ensure_emails_dir()
    # Determine timestamp
    dt = parse_date_to_utc(output.date) or parse_date_to_utc(fallback_header_date) or datetime.now(timezone.utc)
    ts = format_timestamp(dt)
    path = pick_filename(ts, output.message_id)

    # Atomic write
    tmp_path = path + ".tmp"
    data = output.model_dump(by_alias=True)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)
    return path
