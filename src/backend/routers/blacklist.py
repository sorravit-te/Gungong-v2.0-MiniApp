"""Blacklist checking router for bank accounts and phone numbers."""

from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..services.blacklist_service import get_blacklist_service
from ..services.database_service import get_database_service

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class BankCheckRequest(BaseModel):
    """Request model for bank account checking."""
    bank_code: str
    account_number: str
    user_id: Optional[str] = None


class PhoneCheckRequest(BaseModel):
    """Request model for phone number checking."""
    phone_number: str
    user_id: Optional[str] = None


@router.post("/check-bank")
@limiter.limit("20/minute")
async def check_bank(request: Request, bank_request: BankCheckRequest):
    """Check if a bank account is blacklisted."""
    service = get_blacklist_service()
    if not service:
        raise HTTPException(status_code=503, detail="Blacklist service unavailable")
    
    result = service.check_bank_account(bank_request.bank_code, bank_request.account_number)

    # Save to history if user_id is provided
    if bank_request.user_id:
        try:
            db_service = get_database_service()
            if db_service:
                is_blacklisted = result.get("is_blacklisted", False)
                details = result.get("details", {})
                
                message = f"ตรวจสอบบัญชี: {bank_request.bank_code} {bank_request.account_number}"
                reason = f"พบใน Blacklist: {details.get('category', 'N/A')}" if is_blacklisted else "ไม่พบใน Blacklist"
                
                db_service.save_history(
                    user_id=bank_request.user_id,
                    message=message,
                    classification="BLACKLIST_MATCH" if is_blacklisted else "SAFE_NORMAL",
                    is_fraud=is_blacklisted,
                    is_safe=not is_blacklisted,
                    confidence_score=1.0 if is_blacklisted else 0.0,
                    reason=reason,
                    reasoning_summary=f"ตรวจสอบบัญชีธนาคาร {bank_request.bank_code}",
                    model_used="blacklist_database",
                    message_type="bank"
                )
        except Exception as e:
            print(f"⚠️ Failed to save bank check history: {e}")

    return result


@router.post("/check-phone")
@limiter.limit("20/minute")
async def check_phone(request: Request, phone_request: PhoneCheckRequest):
    """Check if a phone number is blacklisted."""
    service = get_blacklist_service()
    if not service:
        raise HTTPException(status_code=503, detail="Blacklist service unavailable")
    
    result = service.check_phone_number(phone_request.phone_number)

    # Save to history if user_id is provided
    if phone_request.user_id:
        try:
            db_service = get_database_service()
            if db_service:
                is_blacklisted = result.get("is_blacklisted", False)
                details = result.get("details", {})
                
                message = f"ตรวจสอบเบอร์: {phone_request.phone_number}"
                reason = f"พบใน Blacklist: {details.get('category', 'N/A')}" if is_blacklisted else "ไม่พบใน Blacklist"
                
                db_service.save_history(
                    user_id=phone_request.user_id,
                    message=message,
                    classification="BLACKLIST_MATCH" if is_blacklisted else "SAFE_NORMAL",
                    is_fraud=is_blacklisted,
                    is_safe=not is_blacklisted,
                    confidence_score=1.0 if is_blacklisted else 0.0,
                    reason=reason,
                    reasoning_summary=f"ตรวจสอบเบอร์โทรศัพท์",
                    model_used="blacklist_database",
                    message_type="phone"
                )
        except Exception as e:
            print(f"⚠️ Failed to save phone check history: {e}")

    return result
