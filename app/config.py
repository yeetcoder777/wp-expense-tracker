from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WhatsApp Expense Tracker"
    environment: str = "development"

    groq_api_key: str
    groq_model: str = "openai/gpt-oss-20b"
    groq_vision_model: str | None = None

    intent_classifier: Literal["groq", "jev"] = "groq"
    typesafe_api_key: str | None = None
    jev_model: str = "jev-1.14.0"
    jev_timeout_seconds: float = Field(default=4.0, gt=0, le=30, allow_inf_nan=False)
    jev_min_confidence: float = Field(default=0.6, ge=0, le=1, allow_inf_nan=False)
    jev_fallback_to_groq: bool = True

    extraction_provider: Literal["groq", "gliner2"] = "groq"
    gliner2_model_id: str = "fastino/gliner2-base-v1"
    gliner2_revision: str = "f9634218e53580c56edf0de97ca1a7d3f1c2354e"
    gliner2_local_files_only: bool = False
    gliner2_entity_threshold: float = Field(default=0.4, gt=0, le=1, allow_inf_nan=False)
    gliner2_classification_threshold: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    gliner2_num_threads: int = Field(default=4, ge=1, le=16)
    gliner2_fallback_to_groq: bool = False

    database_url: str

    dashboard_api_token: str | None = None
    dashboard_user_id: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None
    twilio_webhook_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
