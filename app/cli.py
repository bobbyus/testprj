from __future__ import annotations

import os
import sys
import click
from typing import Dict, Optional
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

from .imap_reader import IMAPReader, env_bool
from .forward_parser import get_original_message_and_headers
from .body_extractor import extract_text
from .openai_client import OpenAIEmailProcessor
from .file_store import write_email_json
from .models import EmailOutput


@click.group()
def cli() -> None:
    """IMAP email processor CLI"""


@cli.command()
@click.option("--limit", type=int, default=None, help="Limit number of emails to process")
def run(limit: Optional[int]) -> None:
    """Process unread emails and write per-email JSON files."""
    load_dotenv()
    host = os.getenv("IMAP_HOST", "localhost")
    port = int(os.getenv("IMAP_PORT", "993"))
    ssl = env_bool("IMAP_SSL", True)
    username = os.getenv("IMAP_USERNAME", "")
    password = os.getenv("IMAP_PASSWORD", "")
    folder = os.getenv("IMAP_FOLDER", "INBOX")
    env_limit = os.getenv("LIMIT")
    if limit is None and env_limit:
        try:
            limit = int(env_limit)
        except ValueError:
            pass

    if not username or not password:
        click.echo("IMAP_USERNAME and IMAP_PASSWORD must be set", err=True)
        sys.exit(1)

    mark_seen = env_bool("MARK_SEEN", True)

    reader = IMAPReader(host, port, ssl, username, password, folder)
    processor: Optional[OpenAIEmailProcessor] = None

    try:
        reader.connect()
        uids = reader.search_unseen(limit=limit)
        click.echo(f"Found {len(uids)} unread message(s) in {folder}")
        for uid in uids:
            try:
                msg = reader.fetch_message(uid)
                original_msg, inline_headers, cleaned_text, method = get_original_message_and_headers(msg)

                # Construct headers from chosen source
                headers: Dict[str, str] = {}
                def get_header(m: EmailMessage, name: str) -> Optional[str]:
                    v = m.get(name)
                    return v if v is not None else None

                if inline_headers:
                    # Use inline forwarded headers preferentially
                    for k in ["From", "To", "Subject", "Date", "Message-Id"]:
                        val = inline_headers.get(k) or inline_headers.get(k.title()) or inline_headers.get(k.upper())
                        if val:
                            headers[k] = val
                    # fill missing from original message
                    for k in ["From", "To", "Subject", "Date", "Message-Id"]:
                        if k not in headers:
                            v = get_header(original_msg, k)
                            if v:
                                headers[k] = v
                else:
                    # use original message headers (either inner rfc822 or top-level)
                    for k in ["From", "To", "Subject", "Date", "Message-Id"]:
                        v = get_header(original_msg, k)
                        if v:
                            headers[k] = v

                # Extract text body from appropriate source
                if cleaned_text is not None:
                    body_text = cleaned_text
                else:
                    body_text = extract_text(original_msg)

                # Build OpenAI processor when first needed
                if processor is None:
                    processor = OpenAIEmailProcessor()

                result: EmailOutput = processor.analyze(headers, body_text)

                # Fill missing fields from headers/body
                if not result.subject:
                    result.subject = headers.get("Subject")
                if not result.message_id:
                    result.message_id = headers.get("Message-Id") or headers.get("Message-ID")
                if not result.date:
                    result.date = headers.get("Date")
                if not result.text:
                    # Include the body_text as fallback
                    result.text = body_text

                out_path = write_email_json(result, fallback_header_date=headers.get("Date"))
                click.echo(f"Processed UID {uid.decode()}: {out_path}")

                if mark_seen:
                    reader.mark_seen(uid)
            except Exception as e:
                click.echo(f"Error processing UID {uid.decode()}: {e}", err=True)
                continue
    finally:
        reader.close()


if __name__ == "__main__":
    cli()
