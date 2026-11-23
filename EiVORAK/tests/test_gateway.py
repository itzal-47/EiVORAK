import hashlib
import hmac
import json
from types import SimpleNamespace

from eivorak.app import create_app
from eivorak.config import Settings
from eivorak.gateway import Gateway


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resposta."))])


def _settings(path):
    return Settings("verify", "page", "meta-secret", "groq", "pair", "", 5000, str(path))


def _payload(message):
    return {"entry": [{"messaging": [{"sender": {"id": "42"}, "message": message}]}]}


def _signature(body, secret="meta-secret"):
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_webhook_accepts_valid_signature_and_rejects_invalid(tmp_path):
    sent = []
    app = create_app(_settings(tmp_path / "db.sqlite"), FakeProvider(), sender=lambda *args: sent.append(args), worker_enabled=False)
    client = app.test_client()
    body = json.dumps(_payload({"mid": "mid-1", "text": "Olá"})).encode()
    rejected = client.post("/webhook", data=body, headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=bad"})
    accepted = client.post("/webhook", data=body, headers={"Content-Type": "application/json", "X-Hub-Signature-256": _signature(body)})
    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert app.extensions["eivorak_gateway"].queue.qsize() == 1


def test_duplicate_mid_is_queued_and_processed_once(tmp_path):
    provider = FakeProvider()
    sent = []
    app = create_app(_settings(tmp_path / "db.sqlite"), provider, sender=lambda *args: sent.append(args), worker_enabled=False)
    gateway = app.extensions["eivorak_gateway"]
    payload = _payload({"mid": "same-id", "text": "Olá"})
    assert gateway.enqueue_payload(payload) == 1
    assert gateway.enqueue_payload(payload) == 0
    assert gateway.process_next()
    assert len(provider.calls) == 1
    assert sent == [("42", "Resposta.")]


def test_rate_limit_and_attachment_reply(tmp_path):
    responses = []
    sent = []
    gateway = Gateway(lambda key, text: responses.append(text) or "ok", lambda *args: sent.append(args), messages_per_minute=1, worker_enabled=False)
    gateway.enqueue_payload(_payload({"mid": "one", "text": "Primeira"}))
    gateway.enqueue_payload(_payload({"mid": "two", "text": "Segunda"}))
    gateway.process_next()
    gateway.process_next()
    assert responses == ["Primeira"]
    assert "muitas mensagens" in sent[1][1]

    attachment_gateway = Gateway(lambda key, text: "unused", lambda *args: sent.append(args), worker_enabled=False)
    attachment_gateway.enqueue_payload(_payload({"mid": "three", "attachments": [{"type": "image"}]}))
    attachment_gateway.process_next()
    assert "anexo" in sent[-1][1]
