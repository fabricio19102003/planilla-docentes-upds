import pytest

from app.config import Settings


OPTIONAL_EMAIL_SETTINGS = (
    "ADMIN_DEFAULT_PASSWORD",
    "RESEND_API_KEY",
    "RESEND_FROM_EMAIL",
    "EMAIL_TEST_RECIPIENT",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_API_KEY_SID",
    "TWILIO_API_KEY_SECRET",
    "TWILIO_WHATSAPP_SANDBOX_FROM",
    "TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT",
)


def build_settings():
    return Settings(
        _env_file=None,
        DATABASE_URL="sqlite:///test.db",
        ASYNC_DATABASE_URL="sqlite+aiosqlite:///test.db",
    )


def test_email_config_defaults_to_disabled_without_resend_credentials(monkeypatch):
    for field in OPTIONAL_EMAIL_SETTINGS:
        monkeypatch.delenv(field, raising=False)

    settings = build_settings()

    assert settings.EMAIL_ENABLED is False
    assert settings.RESEND_API_KEY is None
    assert settings.RESEND_FROM_EMAIL is None
    assert settings.EMAIL_TEST_RECIPIENT is None
    assert settings.ADMIN_DEFAULT_PASSWORD is None
    assert settings.RESEND_API_URL == "https://api.resend.com"
    assert settings.EMAIL_TIMEOUT_SECONDS == 3.0
    assert settings.WHATSAPP_ENABLED is False
    assert settings.WHATSAPP_MODE == "sandbox"
    assert settings.TWILIO_ACCOUNT_SID is None
    assert settings.TWILIO_API_KEY_SID is None
    assert settings.TWILIO_API_KEY_SECRET is None
    assert settings.TWILIO_WHATSAPP_SANDBOX_FROM is None
    assert settings.TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT is None


@pytest.mark.parametrize("blank_value", ["", " \t "])
def test_optional_email_config_normalizes_blank_env_values(monkeypatch, blank_value):
    for field in OPTIONAL_EMAIL_SETTINGS:
        monkeypatch.setenv(field, blank_value)

    settings = build_settings()

    for field in OPTIONAL_EMAIL_SETTINGS:
        assert getattr(settings, field) is None


def test_optional_email_config_preserves_valid_env_values(monkeypatch):
    expected = {
        "ADMIN_DEFAULT_PASSWORD": "  test-admin-password  ",
        "RESEND_API_KEY": "  test-api-key  ",
        "RESEND_FROM_EMAIL": "sender@example.com",
        "EMAIL_TEST_RECIPIENT": "recipient@example.com",
        "TWILIO_ACCOUNT_SID": "AC-test",
        "TWILIO_API_KEY_SID": "SK-test",
        "TWILIO_API_KEY_SECRET": "secret-test",
        "TWILIO_WHATSAPP_SANDBOX_FROM": "+14155238886",
        "TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT": "+59170000000",
    }
    for field, value in expected.items():
        monkeypatch.setenv(field, value)

    settings = build_settings()

    for field, value in expected.items():
        assert getattr(settings, field) == value


def test_whatsapp_production_mode_is_rejected_by_sandbox_release():
    with pytest.raises(ValueError, match="WHATSAPP_MODE"):
        Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            ASYNC_DATABASE_URL="sqlite+aiosqlite:///test.db",
            WHATSAPP_MODE="production",
        )
