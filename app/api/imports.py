from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.auth import require_dashboard_user
from app.db.database import get_db
from app.schemas.features import ImportConfirm
from app.services.import_service import (
    commit_import,
    find_duplicate_rows,
    parse_bank_csv,
)
from app.services.llm_service import extract_receipt_transactions
from app.services.notification_service import send_whatsapp_message

router = APIRouter(prefix="/api/imports", tags=["imports"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File must be 10 MB or smaller")
    return content


@router.post("/csv/preview")
async def preview_csv(
    file: UploadFile = File(...),
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a .csv bank statement")
    content = await _read_upload(file)
    try:
        transactions, errors = parse_bank_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    previews = []
    duplicate_flags = find_duplicate_rows(db, user_id, transactions)
    for transaction, is_duplicate in zip(transactions, duplicate_flags):
        item = transaction.model_dump(mode="json")
        item["possible_duplicate"] = is_duplicate
        previews.append(item)
    return {
        "source_name": file.filename,
        "transactions": previews,
        "errors": errors,
        "valid_count": len(transactions),
        "possible_duplicate_count": sum(item["possible_duplicate"] for item in previews),
    }


@router.post("/receipt/preview")
async def preview_receipt(
    file: UploadFile = File(...),
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_RECEIPT_TYPES:
        raise HTTPException(status_code=415, detail="Receipt must be JPEG, PNG, or WebP")
    content = await _read_upload(file)
    try:
        transactions = extract_receipt_transactions(content, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Receipt extraction service is unavailable") from exc
    previews = []
    duplicate_flags = find_duplicate_rows(db, user_id, transactions)
    for transaction, is_duplicate in zip(transactions, duplicate_flags):
        item = transaction.model_dump(mode="json")
        item["possible_duplicate"] = is_duplicate
        previews.append(item)
    return {
        "source_name": file.filename or "receipt image",
        "transactions": previews,
        "possible_duplicate_count": sum(item["possible_duplicate"] for item in previews),
        "review_required": True,
    }


@router.post("/confirm")
def confirm_import(
    payload: ImportConfirm,
    user_id: str = Depends(require_dashboard_user),
    db: Session = Depends(get_db),
):
    result = commit_import(
        db,
        user_id,
        payload.transactions,
        payload.source_name,
        payload.skip_possible_duplicates,
    )
    if result["budget_alerts"]:
        send_whatsapp_message(user_id, "\n".join(result["budget_alerts"]))
    return result
