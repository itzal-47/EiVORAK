"""Flask entry point and Messenger webhook."""

import logging
from typing import Any

from flask import Flask, request
from groq import Groq

from .brain import Brain
from .config import Settings, load_settings
from .memory.db import init_db

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, provider: Any | None = None) -> Flask:
    """Create the web application and initialise its database once."""
    configuration = settings or load_settings()
    init_db(configuration.database_path)
    llm = provider or Groq(api_key=configuration.groq_api_key)
    brain = Brain(configuration.database_path, llm, configuration.creator_info)
    app = Flask(__name__)
    app.extensions["eivorak_brain"] = brain

    @app.get("/")
    def status() -> tuple[str, int]:
        return "ËiVORAK activo", 200

    @app.route("/webhook", methods=["GET", "POST"])
    def webhook() -> tuple[str, int]:
        if request.method == "GET":
            if request.args.get("hub.verify_token") == configuration.verify_token:
                return request.args.get("hub.challenge", ""), 200
            return "Token inválido", 403
        data = request.get_json(silent=True) or {}
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                message = event.get("message")
                sender = event.get("sender", {}).get("id")
                if not message or not sender or message.get("is_echo"):
                    continue
                if "text" not in message:
                    reply = "Recebi o teu anexo, mas por agora só consigo processar mensagens de texto."
                else:
                    reply = brain.answer(f"messenger:{sender}", str(message["text"]))
                _send_message(configuration, str(sender), reply)
        return "OK", 200

    return app


def _send_message(settings: Settings, recipient: str, text: str) -> None:
    """Send a text reply through Meta's Graph API."""
    import requests

    try:
        response = requests.post(
            "https://graph.facebook.com/v23.0/me/messages",
            params={"access_token": settings.page_access_token},
            json={"recipient": {"id": recipient}, "message": {"text": text[:2000]}},
            timeout=8,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Falha ao enviar resposta ao Messenger")
