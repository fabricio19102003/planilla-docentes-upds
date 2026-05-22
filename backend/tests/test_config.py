from app.config import Settings


def test_email_config_defaults_to_disabled_without_resend_credentials():
    settings = Settings(
        DATABASE_URL="sqlite:///test.db",
        ASYNC_DATABASE_URL="sqlite+aiosqlite:///test.db",
    )

    assert settings.EMAIL_ENABLED is False
    assert settings.RESEND_API_KEY is None
    assert settings.RESEND_FROM_EMAIL is None
    assert settings.RESEND_API_URL == "https://api.resend.com"
    assert settings.EMAIL_TIMEOUT_SECONDS == 3.0
