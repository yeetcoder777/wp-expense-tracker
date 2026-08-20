from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    transaction_type: Literal["expense", "income"]
    amount: Decimal = Field(gt=0)
    currency: str = "INR"
    person: str | None = None
    purpose: str | None = None
    category: str | None = None
    transaction_date: date | None = None