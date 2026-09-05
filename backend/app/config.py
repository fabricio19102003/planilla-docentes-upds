from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Literal, Optional
import json


class Settings(BaseSettings):
    DATABASE_URL: str
    ASYNC_DATABASE_URL: str
    CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'
    UPLOAD_DIR: str = "./data/uploads"

    # App metadata
    APP_TITLE: str = "SIPAD — Sistema Integrado de Pago Docente"
    APP_DESCRIPTION: str = "Sistema de gestión de planilla docente para UPDS Medicina"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    # Development keeps the legacy convenience bootstrap. Production must run
    # Alembic as a separate gate and set this to false.
    AUTO_SCHEMA_BOOTSTRAP: bool = True

    # Payroll constants
    # NOTE: HOURLY_RATE, COMPANY_NAME, COMPANY_NIT, and ACTIVE_ACADEMIC_PERIOD
    # are now stored in the ``app_settings`` table and managed from the admin
    # Configuración page.  Default values are seeded on first startup.
    TOLERANCE_MINUTES: int = 5  # Minutos de tolerancia para asistencia

    # JWT / Auth
    JWT_SECRET: str = "planilla-docentes-upds-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 horas

    # Admin bootstrap — password for seed admin accounts (read by auth_service)
    ADMIN_DEFAULT_PASSWORD: Optional[str] = None

    # Docente bootstrap — temporary password for docente accounts created from designation uploads.
    # Users are forced to change it on first login via must_change_password=True.
    DOCENTE_DEFAULT_PASSWORD: str = "upds*2026"

    # Outbound email / Resend integration
    # Disabled by default so billing publication never requires provider credentials.
    EMAIL_ENABLED: bool = False
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: Optional[str] = None
    RESEND_API_URL: str = "https://api.resend.com"
    EMAIL_TIMEOUT_SECONDS: float = 3.0

    # Test mode — redirects ALL outbound emails to a single recipient.
    # When enabled, only ONE email is sent (first eligible docente) to verify
    # the email flow without spamming real docentes.
    EMAIL_TEST_MODE: bool = False
    EMAIL_TEST_RECIPIENT: Optional[str] = None

    # WhatsApp / Twilio Sandbox. Production senders intentionally require a
    # separate future configuration contract so a Sandbox release cannot be
    # switched to a real sender by changing only a phone number.
    WHATSAPP_ENABLED: bool = False
    # Official production dispatch is separately gated from the legacy Sandbox.
    # Both flags default false so configuration alone cannot enable sending.
    OFFICIAL_WHATSAPP_ENABLED: bool = False
    WHATSAPP_DISPATCH_ENABLED: bool = False
    WHATSAPP_MODE: Literal["sandbox"] = "sandbox"
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_API_KEY_SID: Optional[str] = None
    TWILIO_API_KEY_SECRET: Optional[str] = None
    TWILIO_WHATSAPP_SANDBOX_FROM: Optional[str] = None
    TWILIO_OFFICIAL_FROM: Optional[str] = None
    TWILIO_STATUS_CALLBACK_URL: Optional[str] = None
    TWILIO_INBOUND_CALLBACK_URL: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT: Optional[str] = None
    TWILIO_API_BASE_URL: str = "https://api.twilio.com"
    WHATSAPP_TIMEOUT_SECONDS: float = 3.0

    @field_validator(
        "ADMIN_DEFAULT_PASSWORD",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "EMAIL_TEST_RECIPIENT",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_API_KEY_SID",
        "TWILIO_API_KEY_SECRET",
        "TWILIO_WHATSAPP_SANDBOX_FROM",
        "TWILIO_OFFICIAL_FROM",
        "TWILIO_STATUS_CALLBACK_URL",
        "TWILIO_INBOUND_CALLBACK_URL",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT",
        mode="before",
    )
    @classmethod
    def normalize_blank_optional_strings(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS from JSON string to list."""
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
