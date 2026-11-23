import sqlite3
from types import SimpleNamespace

from eivorak.brain import Brain
from eivorak.memory.db import get_history, init_db, save_message


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resposta curta."))])


def test_current_user_message_is_not_duplicated_in_prompt(tmp_path):
    path = tmp_path / "brain.db"
    init_db(path)
    provider = FakeProvider()
    assert Brain(str(path), provider).answer("messenger:42", "Pergunta") == "Resposta curta."
    messages = provider.calls[0]["messages"]
    assert [message["content"] for message in messages].count("Pergunta") == 1


def test_length_finish_reason_requests_continuation(tmp_path):
    path = tmp_path / "continuation.db"
    init_db(path)

    class ContinuingProvider:
        def __init__(self):
            self.calls = []
            self.results = iter((
                SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Parte inicial sem terminar"), finish_reason="length")]),
                SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="e continuação completa."), finish_reason="stop")]),
            ))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return next(self.results)

    provider = ContinuingProvider()
    reply = Brain(str(path), provider).answer("messenger:42", "Continua")
    assert len(provider.calls) == 2
    assert provider.calls[0]["max_tokens"] >= 2048
    assert "Continua exactamente" in provider.calls[1]["messages"][-1]["content"]
    assert reply == "Parte inicial sem terminar e continuação completa."


def test_privacy_commands_show_data_and_require_apagar_confirmation(tmp_path):
    path = tmp_path / "privacy.db"
    init_db(path)
    user_key = "messenger:42"
    save_message(str(path), user_key, "user", "Olá")
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE users SET first_name = ? WHERE user_key = ?", ("Ana", user_key))
    brain = Brain(str(path), FakeProvider())

    details = brain.answer(user_key, "/meusdados")
    assert "Primeira vez:" in details
    assert "Mensagens: 1" in details
    assert "Nome: Ana" in details

    confirmation = brain.answer(user_key, "/apagar")
    assert "/apagar sim" in confirmation
    assert get_history(str(path), user_key) == [{"role": "user", "content": "Olá"}]

    assert "apagados" in brain.answer(user_key, "/apagar sim")
    assert get_history(str(path), user_key) == []


def test_legacy_delete_phrases_delete_without_confirmation(tmp_path):
    path = tmp_path / "legacy-delete.db"
    init_db(path)
    user_key = "messenger:42"
    save_message(str(path), user_key, "user", "Olá")
    reply = Brain(str(path), FakeProvider()).answer(user_key, "apagar meus dados")
    assert "apagados" in reply
    assert get_history(str(path), user_key) == []
