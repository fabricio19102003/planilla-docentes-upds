from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json


class Settings(BaseSettings):
    DATABASE_URL: str
    ASYNC_DATABASE_URL: str
    CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'
    UPLOAD_DIR: str = "./data/uploads"

    # App metadata
    APP_TITLE: str = "Planilla Docentes UPDS API"
    APP_DESCRIPTION: str = "Sistema de gestión de planilla docente para UPDS Medicina"
    APP_VERSION: str = "1.0.0"

    # Payroll constants
    HOURLY_RATE: float = 70.0  # Bs/hora académica
    TOLERANCE_MINUTES: int = 5  # Minutos de tolerancia para asistencia

    # JWT / Auth
    JWT_SECRET: str = "planilla-docentes-upds-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 horas

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
