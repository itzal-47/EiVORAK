"""Deterministic admin pairing, commands, and on-demand CSV exports."""

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
from io import StringIO
import logging

from .memory.db import connect_db, get_history

logger = logging.getLogger(__name__)
MAX_EXPORT_BYTES = 20 * 1024 * 1024
PRIVILEGED_COMMANDS = frozenset({"/ajuda", "/stats", "/utilizadores", "/conversa", "/exportar"})
ADMIN_HELP = (
    "Comandos de admin: /ajuda, /stats, /utilizadores [n], "
    "/conversa <user_key> [n], /exportar [utilizadores|conversas|tudo]."
)


@dataclass(frozen=True)
class FileAttachment:
    filename: str
    content: bytes
    content_type: str = "text/csv"


@dataclass(frozen=True)
class AdminResponse:
    text: str
    attachment: FileAttachment | None = None


class AdminService:
    """Handle pairing and admin operations without invoking the language model."""

    def __init__(self, database_path: str, pairing_secret: str) -> None:
        self.database_path = database_path
        self.pairing_secret = pairing_secret

    def is_admin(self, user_key: str) -> bool:
        with connect_db(self.database_path) as connection:
            return connection.execute(
                "SELECT 1 FROM admins WHERE user_key = ?", (user_key,)
            ).fetchone() is not None

    def handle(self, user_key: str, text: str) -> AdminResponse | None:
        """Return a deterministic response when the input is an admin command."""
        parts = text.strip().split()
        if not parts:
            return None
        command = parts[0].casefold()
        if command == "/admin":
            return self._pair(user_key, parts[1] if len(parts) == 2 else None)
        if command not in PRIVILEGED_COMMANDS:
            return None

        if not self.is_admin(user_key):
            self._audit(user_key, command)
            return AdminResponse("Esse comando só está disponível para um admin emparelhado.")

        self._audit(user_key, text.strip()[:500])
        if command == "/ajuda":
            return AdminResponse(ADMIN_HELP)
        if command == "/stats":
            return AdminResponse(self._stats())
        if command == "/utilizadores":
            count, error = self._parse_count(parts[1:], default=10)
            return AdminResponse(error or self._users(count))
        if command == "/conversa":
            if len(parts) < 2:
                return AdminResponse("Formato: /conversa <user_key> [n]")
            count, error = self._parse_count(parts[2:], default=10)
            return AdminResponse(error or self._conversation(parts[1], count))
        return self._export(parts[1].casefold() if len(parts) > 1 else "tudo")

    def _pair(self, user_key: str, supplied_code: str | None) -> AdminResponse:
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=1)).isoformat()
        timestamp = now.isoformat()
        with connect_db(self.database_path) as connection:
            connection.execute("DELETE FROM admin_attempts WHERE attempted_at < ?", (cutoff,))
            attempts = connection.execute(
                "SELECT COUNT(*) FROM admin_attempts WHERE user_key = ? AND attempted_at >= ?",
                (user_key, cutoff),
            ).fetchone()[0]
            command = "/admin [emparelhamento]"
            if attempts >= 5:
                connection.execute(
                    "INSERT INTO audit_log(timestamp, user_key, command) VALUES (?, ?, ?)",
                    (timestamp, user_key, command),
                )
                return AdminResponse("Atingiste o limite de tentativas. Tenta novamente dentro de uma hora.")

            if supplied_code is not None and hmac.compare_digest(
                supplied_code.encode("utf-8"), self.pairing_secret.encode("utf-8")
            ):
                connection.execute(
                    "INSERT OR IGNORE INTO admins(user_key, paired_at) VALUES (?, ?)",
                    (user_key, timestamp),
                )
                connection.execute(
                    "INSERT INTO audit_log(timestamp, user_key, command) VALUES (?, ?, ?)",
                    (timestamp, user_key, command),
                )
                return AdminResponse("Emparelhamento concluído. Já tens acesso aos comandos de admin.")

            connection.execute(
                "INSERT INTO admin_attempts(user_key, attempted_at) VALUES (?, ?)",
                (user_key, timestamp),
            )
            connection.execute(
                "INSERT INTO audit_log(timestamp, user_key, command) VALUES (?, ?, ?)",
                (timestamp, user_key, command),
            )
        return AdminResponse("Código de admin inválido.")

    def _audit(self, user_key: str, command: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with connect_db(self.database_path) as connection:
            connection.execute(
                "INSERT INTO audit_log(timestamp, user_key, command) VALUES (?, ?, ?)",
                (timestamp, user_key, command),
            )

    @staticmethod
    def _parse_count(arguments: list[str], *, default: int) -> tuple[int, str | None]:
        if len(arguments) > 1:
            return default, "Indica apenas um número de resultados (máximo 30)."
        if not arguments:
            return default, None
        try:
            requested = int(arguments[0])
        except ValueError:
            return default, "O número de resultados deve ser inteiro."
        if requested < 1:
            return default, "O número de resultados deve ser pelo menos 1."
        return min(requested, 30), None

    def _stats(self) -> str:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        with connect_db(self.database_path) as connection:
            users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            messages = connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            recent_messages = connection.execute(
                "SELECT COUNT(*) FROM conversations WHERE timestamp >= ?", (cutoff,)
            ).fetchone()[0]
            active_users = connection.execute(
                "SELECT COUNT(*) FROM users WHERE last_seen >= ?", (cutoff,)
            ).fetchone()[0]
        return (
            f"Utilizadores: {users}\nMensagens totais: {messages}\n"
            f"Mensagens nas últimas 24h: {recent_messages}\nUtilizadores ativos nas últimas 24h: {active_users}"
        )

    def _users(self, count: int) -> str:
        with connect_db(self.database_path) as connection:
            rows = connection.execute(
                """SELECT user_key, first_name, message_count, last_seen
                   FROM users ORDER BY message_count DESC, last_seen DESC LIMIT ?""",
                (count,),
            ).fetchall()
        if not rows:
            return "Ainda não há utilizadores registados."
        return "\n".join(
            f"{user_key} — {name or 'sem nome'} — {messages} mensagens — última vez: {last_seen or 'desconhecida'}"
            for user_key, name, messages, last_seen in rows
        )

    def _conversation(self, user_key: str, count: int) -> str:
        history = get_history(self.database_path, user_key, limit=count)
        if not history:
            return "Não encontrei conversas para esse user_key."
        return "\n".join(f"{item['role']}: {item['content']}" for item in history)

    def _export(self, export_type: str) -> AdminResponse:
        if export_type not in {"utilizadores", "conversas", "tudo"}:
            return AdminResponse("Usa /exportar [utilizadores|conversas|tudo].")
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            ("tipo", "user_key", "timestamp", "role", "content", "first_seen", "last_seen", "message_count", "first_name", "notice_sent")
        )
        with connect_db(self.database_path) as connection:
            if export_type in {"utilizadores", "tudo"}:
                rows = connection.execute(
                    """SELECT user_key, first_seen, last_seen, message_count, first_name, notice_sent
                       FROM users ORDER BY user_key"""
                ).fetchall()
                for user_key, first_seen, last_seen, count, first_name, notice_sent in rows:
                    writer.writerow(("utilizador", user_key, "", "", "", first_seen, last_seen, count, first_name or "", notice_sent))
            if export_type in {"conversas", "tudo"}:
                rows = connection.execute(
                    """SELECT user_key, timestamp, role, content
                       FROM conversations ORDER BY id"""
                ).fetchall()
                for user_key, timestamp, role, content in rows:
                    writer.writerow(("conversa", user_key, timestamp, role, content, "", "", "", "", ""))
        content = output.getvalue().encode("utf-8")
        if len(content) > MAX_EXPORT_BYTES:
            return AdminResponse("A exportação ultrapassa o limite de 20 MB. Reduz os dados exportados e tenta novamente.")
        filename = f"eivorak_{export_type}.csv"
        return AdminResponse("Exportação CSV gerada.", FileAttachment(filename, content))
