"""Application configuration loaded from the environment."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    verify_token: str
    page_access_token: str
    meta_app_secret: str
    groq_api_key: str
    admin_pairing_secret: str
    creator_info: str
    port: int
    database_path: str


def load_settings() -> Settings:
    """Load settings, raising a clear error when a required secret is absent."""
    load_dotenv()
    required = (
        "VERIFY_TOKEN",
        "PAGE_ACCESS_TOKEN",
        "META_APP_SECRET",
        "GROQ_API_KEY",
        "ADMIN_PAIRING_SECRET",
    )
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Variáveis de ambiente obrigatórias em falta: " + ", ".join(missing))

    try:
        port = int(os.environ.get("PORT", "5000"))
    except ValueError as exc:
        raise RuntimeError("PORT deve ser um número inteiro") from exc

    return Settings(
        verify_token=os.environ["VERIFY_TOKEN"],
        page_access_token=os.environ["PAGE_ACCESS_TOKEN"],
        meta_app_secret=os.environ["META_APP_SECRET"],
        groq_api_key=os.environ["GROQ_API_KEY"],
        admin_pairing_secret=os.environ["ADMIN_PAIRING_SECRET"],
        creator_info=os.environ.get("CREATOR_INFO", "").strip(),
        port=port,
        database_path=os.environ.get("DATABASE_PATH", "eivorak_brain.db"),
    )
