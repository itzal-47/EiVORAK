from types import SimpleNamespace

import requests

from eivorak.app import _send_message, create_app
from eivorak.config import Settings


def test_groq_client_gets_timeout_and_retry_limits(tmp_path, monkeypatch):
    seen = {}

    def fake_groq(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr("eivorak.app.Groq", fake_groq)
    settings = Settings("verify", "page", "secret", "groq-key", "pair", "", 5000, str(tmp_path / "db.sqlite"))
    create_app(settings=settings, sender=lambda *args: None, worker_enabled=False)
    assert seen["timeout"] == 30
    assert seen["max_retries"] == 1


def test_typing_or_part_failure_does_not_skip_send_or_later_parts(monkeypatch):
    calls = []
    message_attempts = 0

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            nonlocal message_attempts
            if "sender_action" in self.payload and len(calls) == 1:
                raise requests.RequestException("typing failed")
            if "message" in self.payload:
                message_attempts += 1
                if message_attempts == 1:
                    raise requests.RequestException("first part failed")

    def fake_post(url, *, params, json, timeout):
        calls.append(json)
        return Response(json)

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr("eivorak.app.time.sleep", lambda _seconds: None)
    settings = Settings("verify", "page", "secret", "groq-key", "pair", "", 5000, "unused.db")

    _send_message(settings, "42", "X" * 2001)

    assert len([call for call in calls if "message" in call]) == 2
    assert message_attempts == 2
    assert len(calls) == 4
