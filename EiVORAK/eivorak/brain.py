"""Conversation orchestration."""

import logging
from typing import Any

from .memory.db import get_history, save_message, search_knowledge
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)


class Brain:
    def __init__(self, database_path: str, provider: Any, creator_info: str = "") -> None:
        self.database_path = database_path
        self.provider = provider
        self.creator_info = creator_info

    def answer(self, user_key: str, text: str) -> str:
        save_message(self.database_path, user_key, "user", text)
        history = get_history(self.database_path, user_key, limit=10)
        # The just-saved user message is already in history; do not append it twice.
        system = build_system_prompt(self.creator_info)
        known = search_knowledge(self.database_path, text)
        if known:
            system += f"\n\nConhecimento relevante: {known}"
        messages = [{"role": "system", "content": system}, *history]
        try:
            response = self.provider.chat.completions.create(
                model="llama-3.3-70b-versatile", messages=messages, max_tokens=1024, temperature=0.7
            )
            reply = (response.choices[0].message.content or "").strip() or "Não consegui preparar uma resposta agora."
        except Exception:
            logger.exception("Falha ao obter resposta do fornecedor de IA")
            reply = "Tive um problema a pensar. Tenta novamente daqui a pouco."
        save_message(self.database_path, user_key, "assistant", reply)
        return reply
