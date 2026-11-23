"""Conversation orchestration."""

import logging
import re
from typing import Any

from .memory.db import delete_user_data, get_history, get_user_summary, save_message, search_knowledge
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)


class Brain:
    def __init__(self, database_path: str, provider: Any, creator_info: str = "") -> None:
        self.database_path = database_path
        self.provider = provider
        self.creator_info = creator_info

    def answer(self, user_key: str, text: str) -> str:
        command = text.strip().casefold()
        if command == "/meusdados":
            summary = get_user_summary(self.database_path, user_key)
            if summary is None:
                return "Ainda não tenho dados guardados sobre ti."
            name = summary.get("first_name")
            lines = [
                "Estes são os dados guardados sobre ti:",
                f"Primeira vez: {summary['first_seen'] or 'não registada'}",
                f"Mensagens: {summary['message_count']}",
            ]
            if name:
                lines.append(f"Nome: {name}")
            return "\n".join(lines)
        if command == "/apagar":
            return "Queres apagar os teus dados e conversas? Confirma com /apagar sim."
        if command == "/apagar sim" or command in {
            "apagar meus dados", "eliminar meus dados", "/eliminar meus dados"
        }:
            delete_user_data(self.database_path, user_key)
            return "Os teus dados e conversas foram apagados."

        save_message(self.database_path, user_key, "user", text)
        history = get_history(self.database_path, user_key, limit=10)
        # The just-saved user message is already in history; do not append it twice.
        system = build_system_prompt(self.creator_info)
        known = search_knowledge(self.database_path, text)
        if known:
            system += f"\n\nConhecimento relevante: {known}"
        messages = [{"role": "system", "content": system}, *history]
        try:
            reply = self._complete(messages)
        except Exception:
            logger.exception("Falha ao obter resposta do fornecedor de IA")
            reply = "Tive um problema a pensar. Tenta novamente daqui a pouco."
        save_message(self.database_path, user_key, "assistant", reply)
        return reply

    def _complete(self, messages: list[dict[str, str]]) -> str:
        """Request a generous completion and continue once if the model hit its limit."""
        parts: list[str] = []
        current_messages = messages
        for attempt in range(3):
            response = self.provider.chat.completions.create(
                model="llama-3.3-70b-versatile", messages=current_messages,
                max_tokens=2048, temperature=0.7,
            )
            choice = response.choices[0]
            content = (choice.message.content or "").strip()
            if content:
                parts.append(content)
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason != "length":
                break
            if attempt < 2:
                current_messages = [
                    *current_messages,
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": "Continua exactamente de onde paraste, sem repetir o que já disseste."},
                ]
                continue

        reply = " ".join(part for part in parts if part).strip()
        if not reply:
            return "Não consegui preparar uma resposta agora."
        if getattr(choice, "finish_reason", None) == "length":
            complete_sentences = re.findall(r".*?[.!?…](?=\s|$)", reply, flags=re.DOTALL)
            if complete_sentences:
                reply = " ".join(sentence.strip() for sentence in complete_sentences).strip()
            else:
                reply = "Não consegui concluir a resposta. Posso tentar de novo com uma pergunta mais específica."
        return reply
