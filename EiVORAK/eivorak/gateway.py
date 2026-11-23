"""Fast Messenger webhook handoff, deduplication, and rate limiting."""

from collections import OrderedDict, defaultdict, deque
import hmac
import hashlib
import logging
import queue
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)
Sender = Callable[[str, str], None]
Responder = Callable[[str, str], str]


class Gateway:
    """Accept webhook events quickly and process messages on one worker thread."""

    def __init__(
        self,
        responder: Responder,
        sender: Sender,
        *,
        messages_per_minute: int = 20,
        worker_enabled: bool = True,
    ) -> None:
        self.responder = responder
        self.sender = sender
        self.messages_per_minute = messages_per_minute
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._counts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._worker_enabled = worker_enabled
        self._worker_started = False
        if worker_enabled:
            self.start_worker()

    @staticmethod
    def valid_signature(body: bytes, signature: str | None, app_secret: str) -> bool:
        """Check Meta's X-Hub-Signature-256 header using constant-time comparison."""
        if not signature or not signature.startswith("sha256="):
            return False
        digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, f"sha256={digest}")

    def enqueue_payload(self, payload: dict[str, Any]) -> int:
        """Queue eligible inbound messages, returning the number accepted."""
        accepted = 0
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                message = event.get("message")
                sender = event.get("sender", {}).get("id")
                if not message or not sender or message.get("is_echo"):
                    continue
                message_id = message.get("mid")
                if message_id and not self._mark_new(str(message_id)):
                    continue
                self.queue.put({"sender": str(sender), "message": message})
                accepted += 1
        return accepted

    def process_next(self, block: bool = False, timeout: float = 0.0) -> bool:
        """Process one queued message; also exposed for deterministic tests."""
        try:
            event = self.queue.get(block=block, timeout=timeout if block else None)
        except queue.Empty:
            return False
        try:
            self._process_event(event)
        except Exception:
            logger.exception("Falha ao processar mensagem do Messenger")
        finally:
            self.queue.task_done()
        return True

    def start_worker(self) -> None:
        """Start a daemon worker exactly once."""
        if self._worker_started:
            return
        self._worker_started = True
        thread = threading.Thread(target=self._worker, name="eivorak-messenger", daemon=True)
        thread.start()

    def _worker(self) -> None:
        while True:
            self.process_next(block=True, timeout=1.0)

    def _mark_new(self, message_id: str) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._seen and (now - next(iter(self._seen.values())) > 86400 or len(self._seen) >= 10000):
                self._seen.popitem(last=False)
            if message_id in self._seen:
                return False
            self._seen[message_id] = now
            return True

    def _allow(self, user_key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            window = self._counts[user_key]
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= self.messages_per_minute:
                return False
            window.append(now)
            return True

    def _process_event(self, event: dict[str, Any]) -> None:
        sender = event["sender"]
        user_key = f"messenger:{sender}"
        if not self._allow(user_key):
            self.sender(sender, "Recebi muitas mensagens tuas num minuto. Aguarda um pouco e tenta novamente.")
            return
        message = event["message"]
        if "text" not in message:
            reply = "Recebi o teu anexo, mas por agora só consigo processar mensagens de texto."
        else:
            reply = self.responder(user_key, str(message["text"]))
        self.sender(sender, reply)
