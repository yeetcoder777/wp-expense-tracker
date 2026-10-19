from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.transaction import Transaction


class TransactionUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    transaction_type: Literal["expense", "income"] | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    person: str | None = Field(default=None, max_length=255)
    purpose: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    transaction_date: date | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_type: str
    amount: Decimal
    currency: str
    person: str | None
    purpose: str | None
    category: str | None
    transaction_date: date | None


class BudgetCreate(BaseModel):
    category: str = Field(default="all", min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=10)

    @field_validator("category", "currency")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    amount: Decimal
    currency: str


class RecurringPaymentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    transaction_type: Literal["expense", "income"] = "expense"
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=10)
    person: str | None = Field(default=None, max_length=255)
    purpose: str | None = Field(default=None, max_length=500)
    category: str = Field(default="bills", min_length=1, max_length=100)
    interval: Literal["weekly", "monthly", "yearly"]
    next_run_date: date
    reminder_days: int = Field(default=1, ge=0, le=30)
    auto_record: bool = False


class RecurringPaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    transaction_type: str
    amount: Decimal
    currency: str
    category: str
    interval: str
    next_run_date: date
    reminder_days: int
    auto_record: bool
    is_active: bool


class ImportConfirm(BaseModel):
    transactions: list[Transaction] = Field(min_length=1, max_length=2000)
    source_name: str = Field(default="manual import", max_length=255)
    skip_possible_duplicates: bool = True


class RecurringPaymentPatch(BaseModel):
    is_active: bool
