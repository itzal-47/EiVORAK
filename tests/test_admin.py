import csv
import io
import sqlite3
from types import SimpleNamespace

from eivorak.admin import AdminResponse, AdminService, FileAttachment
from eivorak.app import create_app
from eivorak.config import Settings
from eivorak.gateway import Gateway
from eivorak.memory.db import get_history, init_db, save_message


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="LLM reply"))])


def test_pairing_success_wrong_code_and_redacted_audit(tmp_path):
    path = tmp_path / "admins.db"
    init_db(path)
    service = AdminService(str(path), "correct-secret")

    wrong = service.handle("messenger:1", "/admin wrong-secret")
    assert wrong and "inválido" in wrong.text
    assert service.is_admin("messenger:1") is False

    paired = service.handle("messenger:1", "/admin correct-secret")
    assert paired and "concluído" in paired.text
    assert service.is_admin("messenger:1") is True
    with sqlite3.connect(path) as connection:
        audit_commands = [row[0] for row in connection.execute("SELECT command FROM audit_log")]
    assert audit_commands == ["/admin [emparelhamento]", "/admin [emparelhamento]"]
    assert "correct-secret" not in " ".join(audit_commands)


def test_pairing_blocks_after_five_wrong_attempts(tmp_path):
    path = tmp_path / "locked.db"
    init_db(path)
    service = AdminService(str(path), "correct-secret")
    for _ in range(5):
        assert "inválido" in service.handle("messenger:1", "/admin bad").text
    blocked = service.handle("messenger:1", "/admin correct-secret")
    assert blocked and "limite" in blocked.text
    assert not service.is_admin("messenger:1")
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM admin_attempts").fetchone()[0]
    assert count == 5


def test_admin_commands_are_refused_to_non_admin_and_audited(tmp_path):
    path = tmp_path / "refused.db"
    init_db(path)
    service = AdminService(str(path), "secret")
    result = service.handle("messenger:unpaired", "/stats")
    assert result and "só está disponível" in result.text
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT user_key, command FROM audit_log").fetchone()
    assert row == ("messenger:unpaired", "/stats")


def test_admin_lists_stats_conversations_and_exports_csv_in_memory(tmp_path):
    path = tmp_path / "exports.db"
    init_db(path)
    user_key = "messenger:visitor"
    save_message(str(path), user_key, "user", "Pergunta privada")
    save_message(str(path), user_key, "assistant", "Resposta privada")
    save_message(str(path), "messenger:formula", "user", "=cmd")
    service = AdminService(str(path), "secret")
    service.handle("messenger:admin", "/admin secret")

    stats = service.handle("messenger:admin", "/stats")
    users = service.handle("messenger:admin", "/utilizadores 99")
    conversation = service.handle("messenger:admin", f"/conversa {user_key} 2")
    assert stats and "Mensagens totais: 3" in stats.text
    assert users and user_key in users.text
    assert conversation and "Pergunta privada" in conversation.text and "Resposta privada" in conversation.text

    exported = service.handle("messenger:admin", "/exportar conversas")
    assert exported and exported.attachment
    assert exported.attachment.filename == "eivorak_conversas.csv"
    rows = list(csv.reader(io.StringIO(exported.attachment.content.decode("utf-8"))))
    assert rows[0][0:5] == ["tipo", "user_key", "timestamp", "role", "content"]
    assert any(row[0] == "conversa" and row[4] == "Pergunta privada" for row in rows[1:])
    assert any(row[0] == "conversa" and row[4] == "'=cmd" for row in rows[1:])
    user_export = service.handle("messenger:admin", "/exportar utilizadores")
    all_export = service.handle("messenger:admin", "/exportar tudo")
    assert user_export and user_export.attachment
    assert any(
        row[0] == "utilizador" and row[1] == user_key
        for row in csv.reader(io.StringIO(user_export.attachment.content.decode("utf-8")))
    )
    assert all_export and all_export.attachment
    all_rows = list(csv.reader(io.StringIO(all_export.attachment.content.decode("utf-8"))))
    assert {row[0] for row in all_rows[1:]} == {"utilizador", "conversa"}
    assert get_history(str(path), "messenger:admin") == []

    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 7


def test_admin_pairing_command_never_reaches_model_or_conversation(tmp_path):
    path = tmp_path / "app.db"
    settings = Settings("verify", "page", "meta", "groq", "pair-code", "", 5000, str(path))
    provider = FakeProvider()
    sent = []
    app = create_app(settings, provider, sender=lambda *args: sent.append(args), worker_enabled=False)
    gateway = app.extensions["eivorak_gateway"]
    gateway.enqueue_payload({"entry": [{"messaging": [{"sender": {"id": "admin"}, "message": {"mid": "m1", "text": "/admin pair-code"}}]}]})
    gateway.process_next()

    assert provider.calls == []
    assert get_history(str(path), "messenger:admin") == []
    assert any("Emparelhamento concluído" in item[1] for item in sent)
    with sqlite3.connect(path) as connection:
        command = connection.execute("SELECT command FROM audit_log").fetchone()[0]
    assert "pair-code" not in command


def test_admin_is_exempt_from_gateway_rate_limit():
    responses = []
    gateway = Gateway(
        lambda _key, text: responses.append(text) or "ok",
        lambda *_args: None,
        messages_per_minute=1,
        worker_enabled=False,
        admin_check=lambda _key: True,
    )
    for index in range(3):
        gateway.enqueue_payload({"entry": [{"messaging": [{"sender": {"id": "admin"}, "message": {"mid": str(index), "text": "normal"}}]}]})
    for _ in range(3):
        gateway.process_next()
    assert responses == ["normal", "normal", "normal"]


def test_failed_csv_upload_returns_clear_gateway_error():
    sent = []

    def fake_sender(*args):
        sent.append(args)
        return False if len(args) == 3 else None

    gateway = Gateway(
        lambda _key, _text: "unused",
        fake_sender,
        worker_enabled=False,
        command_handler=lambda _key, _text: AdminResponse(
            "Exportação gerada.", FileAttachment("data.csv", b"a,b\n")
        ),
    )
    gateway.enqueue_payload({"entry": [{"messaging": [{"sender": {"id": "admin"}, "message": {"mid": "export", "text": "/exportar"}}]}]})
    gateway.process_next()
    assert sent[-1] == ("admin", "Não consegui enviar o ficheiro CSV. Tenta novamente mais tarde.")
