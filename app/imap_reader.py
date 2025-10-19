from __future__ import annotations

import imaplib
import os
from typing import Generator, Iterable, List, Optional, Tuple
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage


class IMAPReader:
    def __init__(
        self,
        host: str,
        port: int,
        ssl: bool,
        username: str,
        password: str,
        folder: str = "INBOX",
    ) -> None:
        self.host = host
        self.port = port
        self.ssl = ssl
        self.username = username
        self.password = password
        self.folder = folder
        self.conn: Optional[imaplib.IMAP4] = None

    def connect(self) -> None:
        if self.ssl:
            self.conn = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            self.conn = imaplib.IMAP4(self.host, self.port)
        self.conn.login(self.username, self.password)
        typ, data = self.conn.select(self.folder)
        if typ != "OK":
            raise RuntimeError(f"Failed to select folder {self.folder}: {typ} {data}")

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            try:
                self.conn.logout()
            except Exception:
                pass
            self.conn = None

    def _conn_checked(self) -> imaplib.IMAP4:
        if self.conn is None:
            raise RuntimeError("IMAP connection is not established. Call connect() first.")
        return self.conn

    def search_unseen(self, limit: Optional[int] = None) -> List[bytes]:
        conn = self._conn_checked()
        typ, data = conn.uid("SEARCH", None, "UNSEEN")
        if typ != "OK":
            raise RuntimeError(f"UID SEARCH UNSEEN failed: {typ} {data}")
        uids = data[0].split() if data and data[0] else []
        # Newest first? Keep as server returns (usually ascending). We'll process in order.
        if limit is not None:
            uids = uids[:limit]
        return uids

    def fetch_message(self, uid: bytes) -> EmailMessage:
        conn = self._conn_checked()
        # Use BODY.PEEK[] to avoid setting \Seen flag
        typ, data = conn.uid("FETCH", uid, "(BODY.PEEK[])")
        if typ != "OK" or not data or data[0] is None:
            # Some servers return list like [(b'1 (BODY[] {bytes}', b'...'), b')']
            # Try alternative: RFC822
            typ2, data2 = conn.uid("FETCH", uid, "(RFC822)")
            if typ2 != "OK" or not data2 or data2[0] is None:
                raise RuntimeError(f"Failed to fetch message for UID {uid!r}: {typ} {data}")
            raw = data2[0][1]
        else:
            # data may be a list of tuples and a closing b')'
            for part in data:
                if isinstance(part, tuple) and part[1]:
                    raw = part[1]
                    break
            else:
                raise RuntimeError(f"Unexpected FETCH response for UID {uid!r}: {data}")
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        return msg

    def mark_seen(self, uid: bytes) -> None:
        conn = self._conn_checked()
        conn.uid("STORE", uid, "+FLAGS", "(\\Seen)")


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}
