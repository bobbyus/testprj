# IMAP Email Processor with OpenAI

A Python CLI tool that reads unread emails via IMAP, extracts the original message details (handling forwarded messages), sends a compact header/body snippet to OpenAI for structured extraction, and writes one JSON file per processed email under `emails/`.

Key features
- Fetches UNSEEN emails from a single folder (default INBOX)
- Prioritizes the original email inside forwarded messages (embedded message/rfc822 or inline headers)
- Extracts text from text/plain or converts HTML-only emails to text
- Sends data to OpenAI and saves a strict JSON object per email to `emails/` as `YYYYMMDDTHHMMSSZ_<sanitized-message-id>.json`
- Marks emails as SEEN only after successful write (configurable)

## Setup

1) Python 3.10+ recommended. Create and activate a virtual environment:

```
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies:

```
pip install -r requirements.txt
```

3) Copy `.env.example` to `.env` and set your values:

```
cp .env.example .env
```

Required env vars:
- IMAP_HOST, IMAP_PORT, IMAP_SSL (true/false)
- IMAP_USERNAME, IMAP_PASSWORD
- IMAP_FOLDER (default INBOX)
- OPENAI_API_KEY
- OPENAI_MODEL (optional; default gpt-4o-mini)
- MARK_SEEN (optional; default true)
- LIMIT (optional; can also be set via CLI)

## Usage

Run the CLI:

```
python -m app.cli run --limit 10
```

This processes up to 10 unread emails from the configured folder, writes JSON per email into `emails/`, and marks each email as seen after a successful write.

Notes:
- For forwarded emails, the tool extracts From/To from the original message inside the forward. It handles both embedded `message/rfc822` parts and inline forwarded header blocks (e.g., lines starting with `From:`, `To:`, `Subject:`, `Date:` until a blank line). If neither is present, it falls back to the top-level headers and basic heuristics.
- HTML-only emails are converted to text using BeautifulSoup.

## Development

- Entry point: `app/cli.py`
- IMAP helper: `app/imap_reader.py`
- Forwarded parsing logic: `app/forward_parser.py`
- Body extraction: `app/body_extractor.py`
- OpenAI integration: `app/openai_client.py`
- File store: `app/file_store.py`
- Models: `app/models.py`

## Tests

Basic unit tests (optional) are under `tests/`. You can run them with:

```
python -m unittest
```

## Output format

Each processed email produces a JSON file with fields:

```
{
  "from": "Name <email@example.com>",
  "to": ["Recipient <to@example.com>", "CC <cc@example.com>"],
  "subject": "...",
  "text": "plain text content",
  "date": "RFC 3339 if available, else date string",
  "message_id": "..."
}
```

Filename: `YYYYMMDDTHHMMSSZ_<sanitized-message-id>.json`. If the message-id is missing, a stable hash is used instead. If a filename already exists, a numeric suffix is appended.
