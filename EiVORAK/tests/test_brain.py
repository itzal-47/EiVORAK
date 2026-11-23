from types import SimpleNamespace

from eivorak.brain import Brain
from eivorak.memory.db import init_db


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
