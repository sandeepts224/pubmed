from __future__ import annotations

from backend.app.clients.llm import ClaudeClient
from backend.app.core.settings import settings


def main() -> int:
    print(f"Using Claude model: {settings.claude_extraction_model}")
    client = ClaudeClient()
    try:
        resp = client.create_message(
            model=settings.claude_extraction_model,
            system="You are a test helper.",
            user='Return this exact JSON: {"ok": true}',
            max_tokens=50,
        )
        text = ClaudeClient.message_text_content(resp)
        print("SUCCESS response text:")
        print(text)
    except Exception as exc:
        print("FAILED calling Claude:")
        print(type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



