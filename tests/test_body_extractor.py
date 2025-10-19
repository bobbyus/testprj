import unittest
from email.message import EmailMessage

# Guard tests if BeautifulSoup is not installed
try:
    import bs4  # noqa: F401
    BS4_AVAILABLE = True
except Exception:
    BS4_AVAILABLE = False

from app.body_extractor import extract_text


@unittest.skipUnless(BS4_AVAILABLE, "beautifulsoup4 not installed")
class TestBodyExtractor(unittest.TestCase):
    def test_text_plain_preferred(self):
        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg.set_content("This is plain text.")
        msg.add_alternative("<p>This is <b>HTML</b>.</p>", subtype="html")
        text = extract_text(msg)
        self.assertIn("This is plain text.", text)

    def test_html_converted(self):
        msg = EmailMessage()
        msg["Subject"] = "HTML Only"
        msg.add_alternative(
            "<html><body><h1>Header</h1><p>Line A</p><p>Line B</p></body></html>", subtype="html"
        )
        text = extract_text(msg)
        # Should contain the HTML text rendered
        self.assertIn("Header", text)
        self.assertIn("Line A", text)
        self.assertIn("Line B", text)


if __name__ == "__main__":
    unittest.main()
