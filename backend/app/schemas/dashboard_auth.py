from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
import re


class LoginStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str = Field(min_length=8, max_length=16)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not re.fullmatch(r"\+[1-9]\d{6,14}", value):
            raise ValueError("Use international format, for example +919876543210")
        return value


class LoginChallengeRead(BaseModel):
    request_id: str
    poll_secret: str
    command: str
    whatsapp_url: str
    expires_at: datetime


class LoginComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=36, max_length=36)
    poll_secret: str = Field(min_length=43, max_length=43)


class AccountRead(BaseModel):
    account_id: str
    whatsapp_number: str
