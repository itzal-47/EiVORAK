"""Split responses into readable channel-sized messages."""

import re

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def _split_long_sentence(sentence: str, max_len: int) -> list[str]:
    """Split an unusually long sentence at word boundaries as a last resort."""
    words = sentence.split()
    parts: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_len:
            # Preserve every character while respecting the channel's hard limit.
            chunks = [word[index : index + max_len] for index in range(0, len(word), max_len)]
        else:
            chunks = [word]
        for chunk in chunks:
            candidate = f"{current} {chunk}".strip()
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    parts.append(current)
                current = chunk
    if current:
        parts.append(current)
    return parts


def split_message(text: str, max_len: int = 2000) -> list[str]:
    """Split by paragraphs and sentence ends, never breaking a normal sentence."""
    if max_len < 1:
        raise ValueError("max_len deve ser maior do que zero")
    content = text.strip()
    if not content:
        return []

    parts: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", content):
        sentences = [item.strip() for item in _SENTENCE_END.split(paragraph.strip()) if item.strip()]
        for sentence_index, sentence in enumerate(sentences):
            if len(sentence) > max_len:
                if current:
                    parts.append(current)
                    current = ""
                parts.extend(_split_long_sentence(sentence, max_len))
                continue
            separator = "\n\n" if sentence_index == 0 else " "
            candidate = f"{current}{separator}{sentence}" if current else sentence
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    parts.append(current)
                current = sentence
    if current:
        parts.append(current)
    return parts
