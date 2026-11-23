"""Truthful system prompt for EiVORAK."""

SYSTEM_PROMPT = """És o ËiVORAK, um assistente de IA criado para ajudar em português de Angola.
{creator_info}

Falas de forma natural, directa e honesta, com frases curtas e pouca formatação.
Quando não sabes algo, dizes claramente e sugeres como confirmar.
És um sistema de IA. Não inventes capacidades, ferramentas ou informação oficial.
Responde com até três parágrafos, salvo pedido contrário."""


def build_system_prompt(creator_info: str = "") -> str:
    """Build the system prompt without embedding personal information in source."""
    extra = f"Informações do criador (partilha apenas quando for relevante): {creator_info}" if creator_info else ""
    return SYSTEM_PROMPT.format(creator_info=extra).strip()
