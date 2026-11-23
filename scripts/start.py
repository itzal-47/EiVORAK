"""Start EiVORAK locally or under Litestream replication."""

import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LITESTREAM_CONFIG = PROJECT_ROOT / "litestream.yml"
LITESTREAM_SETTINGS = (
    "LITESTREAM_ENDPOINT",
    "LITESTREAM_BUCKET",
    "LITESTREAM_ACCESS_KEY_ID",
    "LITESTREAM_SECRET_ACCESS_KEY",
)


def start(
    environment: Mapping[str, str] | None = None,
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    exec_process: Callable[..., object] | None = None,
    database_exists: Callable[[str], bool] | None = None,
) -> int:
    """Run the bot directly or let Litestream restore and supervise it."""
    env = dict(os.environ if environment is None else environment)
    env.setdefault("DATABASE_PATH", "eivorak_brain.db")
    env.setdefault("LITESTREAM_REGION", "us-east-1")
    run_command = run or subprocess.run
    replace_process = exec_process or os.execvpe
    exists = database_exists or os.path.exists
    configured = [bool(env.get(name, "").strip()) for name in LITESTREAM_SETTINGS]

    if not any(configured):
        replace_process("gunicorn", _gunicorn_command(env), env)
        return 0
    if not all(configured):
        missing = [name for name, present in zip(LITESTREAM_SETTINGS, configured) if not present]
        logger.error("Configuração Litestream incompleta; faltam: %s", ", ".join(missing))
        return 2

    database_path = env["DATABASE_PATH"]
    if not exists(database_path):
        restore = [
            "litestream", "restore", "-config", str(LITESTREAM_CONFIG),
            "-if-replica-exists", database_path,
        ]
        try:
            result = run_command(restore, env=env, check=False)
        except OSError:
            logger.exception("Não foi possível executar Litestream para restaurar a base de dados")
            return 127
        if result.returncode:
            logger.error("Litestream falhou ao restaurar a base de dados (código %s)", result.returncode)
            return result.returncode

    app_command = shlex.join(_gunicorn_command(env))
    command = [
        "litestream", "replicate", "-config", str(LITESTREAM_CONFIG),
        "-restore-if-db-not-exists", "-exec", app_command,
    ]
    try:
        replace_process("litestream", command, env)
    except OSError:
        logger.exception("Litestream não está instalado ou não pode ser executado")
        return 127
    return 0


def _gunicorn_command(environment: Mapping[str, str]) -> list[str]:
    """Build the production Gunicorn command for the configured port."""
    port = environment.get("PORT", "5000")
    return [
        "gunicorn", "--workers", "1", "--threads", "4", "--timeout", "120",
        "--bind", f"0.0.0.0:{port}", "eivorak.app:create_app()",
    ]


def main() -> int:
    """Load local environment settings and start the selected mode."""
    logging.basicConfig(level=logging.INFO)
    os.chdir(PROJECT_ROOT)
    load_dotenv(PROJECT_ROOT / ".env")
    return start()


if __name__ == "__main__":
    raise SystemExit(main())
