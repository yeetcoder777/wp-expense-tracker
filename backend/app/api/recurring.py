from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_dashboard_user
from app.db.database import get_db
from app.db.models import RecurringExecution, RecurringPayment
from app.schemas.features import RecurringPaymentCreate, RecurringPaymentPatch, RecurringPaymentRead

router = APIRouter(prefix="/api/recurring", tags=["recurring payments"])


@router.get("", response_model=list[RecurringPaymentRead])
def list_recurring_payments(
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    return db.query(RecurringPayment).filter(
        RecurringPayment.user_id == user_id
    ).order_by(RecurringPayment.next_run_date).all()


@router.post("", response_model=RecurringPaymentRead)
def create_recurring_payment(
    payload: RecurringPaymentCreate,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    values = payload.model_dump()
    values["currency"] = values["currency"].upper()
    values["category"] = values["category"].strip().lower()
    values["anchor_day"] = values["next_run_date"].day
    values["anchor_month"] = values["next_run_date"].month
    payment = RecurringPayment(user_id=user_id, **values)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.patch("/{payment_id}", response_model=RecurringPaymentRead)
def update_recurring_payment(
    payment_id: int,
    payload: RecurringPaymentPatch,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    payment = db.query(RecurringPayment).filter(
        RecurringPayment.id == payment_id,
        RecurringPayment.user_id == user_id,
    ).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Recurring payment not found")
    payment.is_active = payload.is_active
    db.commit()
    db.refresh(payment)
    return payment


@router.delete("/{payment_id}")
def delete_recurring_payment(
    payment_id: int,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    payment = db.query(RecurringPayment).filter(
        RecurringPayment.id == payment_id,
        RecurringPayment.user_id == user_id,
    ).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Recurring payment not found")
    db.query(RecurringExecution).filter(
        RecurringExecution.recurring_payment_id == payment.id
    ).delete()
    db.delete(payment)
    db.commit()
    return {"deleted": True, "id": payment_id}
