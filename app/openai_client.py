from __future__ import annotations

import json
import os
from typing import Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI
from .models import EmailOutput


class OpenAIEmailProcessor:
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.model = os.getenv("OPENAI_MODEL", model)
        self.client = OpenAI(api_key=self.api_key)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def analyze(self, headers: Dict[str, str], body_text: str) -> EmailOutput:
        # Keep prompt compact but precise
        system_msg = (
            "You are a data extraction assistant. Extract metadata from the ORIGINAL email in a possibly forwarded message. "
            "If the message content is a forward, use the ORIGINAL sender and recipients FROM the forwarded content, not the outer envelope. "
            "Output strictly a single JSON object with keys: from, to, subject, text, date, message_id. "
            "The 'to' must be an array of strings (each 'Name <email>' if available). "
            "Use RFC 3339 for 'date' if available; otherwise copy a recognizable date string from headers. "
            "If a field is unavailable, set it to null (for strings) or [] (for to)."
        )
        user_msg = (
            "Headers (may include parsed forwarded headers):\n" +
            "\n".join(f"{k}: {v}" for k, v in headers.items()) +
            "\n\nBody (original message preferred):\n" + body_text[:8000]
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        # Validate and coerce with Pydantic
        output = EmailOutput.model_validate(data)
        return output
