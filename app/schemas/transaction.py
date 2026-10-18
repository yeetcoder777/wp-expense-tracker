from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Transaction(BaseModel):
    transaction_type: Literal["expense", "income"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=1, max_length=10)
    person: str | None = Field(default=None, max_length=255)
    purpose: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    transaction_date: date | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        value = {"₹": "INR", "RS": "INR", "RS.": "INR", "$": "USD", "€": "EUR", "£": "GBP"}.get(value, value)
        if len(value) < 3:
            raise ValueError("currency must be an ISO code or supported currency symbol")
        return value
