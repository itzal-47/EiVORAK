import hashlib
import hmac
import json
from types import SimpleNamespace

from eivorak.admin import AdminResponse
from eivorak.app import create_app
from eivorak.config import Settings
from eivorak.gateway import Gateway
from eivorak.memory.db import claim_privacy_notice, init_db


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
    assert sent == [
        ("42", "Guardo as tuas mensagens para manter o contexto. O criador pode rever conversas para melhorar o bot. Usa /meusdados para ver os dados guardados e /apagar para os apagar. O registo de auditoria de admin mantém-se após /apagar."),
        ("42", "Resposta."),
    ]


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


def test_privacy_notice_is_sent_once_per_user(tmp_path):
    path = tmp_path / "notice.db"
    init_db(path)
    sent = []
    gateway = Gateway(
        lambda _key, text: "Resposta: " + text,
        lambda *args: sent.append(args),
        worker_enabled=False,
        notice=lambda key: "Aviso de privacidade." if claim_privacy_notice(path, key) else None,
    )
    gateway.enqueue_payload(_payload({"mid": "notice-1", "text": "Primeira"}))
    gateway.enqueue_payload(_payload({"mid": "notice-2", "text": "Segunda"}))
    gateway.process_next()
    gateway.process_next()
    assert [text for _recipient, text in sent].count("Aviso de privacidade.") == 1


def test_repeated_admin_command_is_rate_limited_for_non_admin():
    handled = []
    sent = []
    gateway = Gateway(
        lambda _key, _text: "não deve chegar ao modelo",
        lambda _recipient, text: sent.append(text),
        messages_per_minute=1,
        worker_enabled=False,
        command_handler=lambda _key, text: handled.append(text) or AdminResponse("comando recusado"),
    )
    for index in range(2):
        gateway.enqueue_payload(_payload({"mid": f"stats-{index}", "text": "/stats"}))
    gateway.process_next()
    gateway.process_next()
    assert handled == ["/stats"]
    assert sent == [
        "comando recusado",
        "Recebi muitas mensagens tuas num minuto. Aguarda um pouco e tenta novamente.",
    ]


def test_admin_command_is_exempt_from_rate_limit():
    handled = []
    sent = []
    gateway = Gateway(
        lambda _key, _text: "unused",
        lambda _recipient, text: sent.append(text),
        messages_per_minute=1,
        worker_enabled=False,
        command_handler=lambda _key, text: handled.append(text) or AdminResponse("admin ok"),
        admin_check=lambda _key: True,
    )
    for index in range(3):
        gateway.enqueue_payload(_payload({"mid": f"admin-stats-{index}", "text": "/stats"}))
    for _ in range(3):
        gateway.process_next()
    assert handled == ["/stats", "/stats", "/stats"]
    assert sent == ["admin ok", "admin ok", "admin ok"]
