import unittest
from email import policy
from email.parser import BytesParser

# Guard tests if BeautifulSoup is not installed (used by body_extractor)
try:
    import bs4  # noqa: F401
    BS4_AVAILABLE = True
except Exception:
    BS4_AVAILABLE = False

from app.forward_parser import (
    get_original_message_and_headers,
    parse_inline_forwarded_headers,
    strip_header_block_from_text,
)
from app.body_extractor import extract_text


EML_EMBEDDED = (b"\r\n".join([
    b"From: Wrapper <wrapper@example.com>",
    b"To: Someone <someone@example.com>",
    b"Subject: Fwd: Inner Subject",
    b"Date: Fri, 10 Oct 2025 10:20:20 +0000",
    b"MIME-Version: 1.0",
    b"Content-Type: multipart/mixed; boundary=outer",
    b"",
    b"--outer",
    b"Content-Type: text/plain; charset=\"utf-8\"",
    b"",
    b"See forwarded below.",
    b"",
    b"--outer",
    b"Content-Type: message/rfc822",
    b"",
    b"From: Original Sender <sender@example.com>",
    b"To: Recipient One <to1@example.com>, Recipient Two <to2@example.com>",
    b"Subject: Inner Subject",
    b"Date: Fri, 10 Oct 2025 10:10:10 +0000",
    b"Message-Id: <inner123@example.com>",
    b"MIME-Version: 1.0",
    b"Content-Type: text/plain; charset=\"utf-8\"",
    b"",
    b"Inner body text.",
    b"",
    b"--outer--",
    b"",
]))

EML_INLINE = ("\r\n".join([
    "From: Wrapper <wrapper@example.com>",
    "To: Someone <someone@example.com>",
    "Subject: Fwd: Inline Subject",
    "Date: Mon, 12 Oct 2025 12:22:22 +0000",
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=\"utf-8\"",
    "",
    "Hello team, see below.",
    "",
    "---------- Forwarded message ----------",
    "From: Original Sender <sender2@example.com>",
    "To: Forward Recipient <to@example.com>",
    "Subject: Inline Subject",
    "Date: Mon, 12 Oct 2025 12:12:12 +0000",
    "Message-Id: <inline-999@example.com>",
    "",
    "This is the original inline body.",
    "Thanks.",
    "",
    "Regards,",
    "Wrapper",
    "",
]).encode("utf-8"))


@unittest.skipUnless(BS4_AVAILABLE, "beautifulsoup4 not installed")
class TestForwardParser(unittest.TestCase):
    def test_embedded_rfc822_original(self):
        msg = BytesParser(policy=policy.default).parsebytes(EML_EMBEDDED)
        original, inline_headers, cleaned_text, method = get_original_message_and_headers(msg)
        self.assertEqual(method, "rfc822")
        self.assertIsNotNone(original.get("From"))
        self.assertIn("sender@example.com", original.get("From"))
        self.assertIn("to1@example.com", original.get("To"))
        body = extract_text(original)
        self.assertIn("Inner body text", body)

    def test_inline_forward_headers(self):
        msg = BytesParser(policy=policy.default).parsebytes(EML_INLINE)
        # parse via helper directly
        from app.body_extractor import extract_text as extract_outer
        outer_text = extract_outer(msg)
        headers, block_range = parse_inline_forwarded_headers(outer_text)
        self.assertTrue(headers)
        self.assertIn("From", headers)
        self.assertIn("sender2@example.com", headers.get("From"))
        self.assertIn("Forward Recipient", headers.get("To"))
        cleaned = strip_header_block_from_text(outer_text, block_range)
        self.assertIn("original inline body", cleaned)


if __name__ == "__main__":
    unittest.main()
