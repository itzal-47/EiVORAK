"""Flask entry point and Messenger webhook."""

import logging
import time
from typing import Any

from flask import Flask, request
from groq import Groq

from .brain import Brain
from .config import Settings, load_settings
from .gateway import Gateway
from .humanize import split_message
from .memory.db import claim_privacy_notice, init_db

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    provider: Any | None = None,
    *,
    sender: Any | None = None,
    worker_enabled: bool = True,
) -> Flask:
    """Create the web application and initialise its database once."""
    configuration = settings or load_settings()
    init_db(configuration.database_path)
    llm = provider or Groq(api_key=configuration.groq_api_key, timeout=30, max_retries=1)
    brain = Brain(configuration.database_path, llm, configuration.creator_info)
    app = Flask(__name__)
    app.extensions["eivorak_brain"] = brain
    send = sender or (lambda recipient, text: _send_message(configuration, recipient, text))
    def notice_for_user(user_key: str) -> str | None:
        if claim_privacy_notice(configuration.database_path, user_key):
            return (
                "Guardo as tuas mensagens para manter o contexto. O criador pode rever conversas "
                "para melhorar o bot. Usa /meusdados para ver os dados guardados e /apagar para os apagar."
            )
        return None

    gateway = Gateway(brain.answer, send, worker_enabled=worker_enabled, notice=notice_for_user)
    app.extensions["eivorak_gateway"] = gateway

    @app.get("/")
    def status() -> tuple[str, int]:
        return "ËiVORAK activo", 200

    @app.route("/webhook", methods=["GET", "POST"])
    def webhook() -> tuple[str, int]:
        if request.method == "GET":
            if request.args.get("hub.verify_token") == configuration.verify_token:
                return request.args.get("hub.challenge", ""), 200
            return "Token inválido", 403
        body = request.get_data(cache=True)
        signature = request.headers.get("X-Hub-Signature-256")
        if not Gateway.valid_signature(body, signature, configuration.meta_app_secret):
            return "Assinatura inválida", 403
        data = request.get_json(silent=True) or {}
        gateway.enqueue_payload(data)
        return "OK", 200

    return app


def _send_message(settings: Settings, recipient: str, text: str) -> None:
    """Send channel-sized text parts and signal typing before each part."""
    import requests

    for part in split_message(text, max_len=2000):
        try:
            requests.post(
                "https://graph.facebook.com/v23.0/me/messages",
                params={"access_token": settings.page_access_token},
                json={"recipient": {"id": recipient}, "sender_action": "typing_on"},
                timeout=8,
            ).raise_for_status()
            time.sleep(min(0.8, max(0.15, len(part) / 2000)))
        except Exception:
            logger.exception("Falha ao activar typing_on no Messenger")
        try:
            requests.post(
                "https://graph.facebook.com/v23.0/me/messages",
                params={"access_token": settings.page_access_token},
                json={"recipient": {"id": recipient}, "message": {"text": part}},
                timeout=8,
            ).raise_for_status()
        except Exception:
            logger.exception("Falha ao enviar resposta ao Messenger")
