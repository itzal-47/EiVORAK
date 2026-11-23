from eivorak.config import load_settings


def test_required_secrets_are_reported(monkeypatch):
    monkeypatch.setattr("eivorak.config.load_dotenv", lambda: False)
    for name in (
        "VERIFY_TOKEN", "PAGE_ACCESS_TOKEN", "META_APP_SECRET", "GROQ_API_KEY", "ADMIN_PAIRING_SECRET"
    ):
        monkeypatch.delenv(name, raising=False)
    try:
        load_settings()
    except RuntimeError as exc:
        assert "VERIFY_TOKEN" in str(exc)
        assert "META_APP_SECRET" in str(exc)
    else:
        raise AssertionError("load_settings devia falhar sem segredos obrigatórios")


def test_settings_load_without_personal_details(monkeypatch):
    monkeypatch.setattr("eivorak.config.load_dotenv", lambda: False)
    values = {
        "VERIFY_TOKEN": "verify", "PAGE_ACCESS_TOKEN": "page", "META_APP_SECRET": "meta",
        "GROQ_API_KEY": "groq", "ADMIN_PAIRING_SECRET": "pair",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("CREATOR_INFO", raising=False)
    monkeypatch.setenv("DATABASE_PATH", ":memory:")
    settings = load_settings()
    assert settings.creator_info == ""
    assert settings.database_path == ":memory:"
