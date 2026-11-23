from eivorak.humanize import split_message


def test_short_message_is_left_as_one_part():
    assert split_message("Olá. Tudo bem?", max_len=100) == ["Olá. Tudo bem?"]


def test_long_message_splits_at_sentence_boundaries_and_respects_limit():
    sentences = ["A primeira resposta termina aqui.", "A segunda também termina aqui.", "A terceira fica completa."]
    parts = split_message(" ".join(sentences), max_len=42)
    assert len(parts) > 1
    assert all(len(part) <= 42 for part in parts)
    assert " ".join(parts) == " ".join(sentences)
    assert all(part.endswith((".", "!", "?")) for part in parts)
