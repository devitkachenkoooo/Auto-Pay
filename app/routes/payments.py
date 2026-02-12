from fastapi import APIRouter, Depends, Request
from app.schemas.transaction import WebhookPayload
from app.security import verify_hmac_signature
from app.services.payment_service import PaymentService
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize limiter for this router
limiter = Limiter(key_func=get_remote_address)


@router.post("/webhook/payment", dependencies=[Depends(verify_hmac_signature)])
async def process_payment(request: Request, payload: WebhookPayload):
    """Main webhook endpoint for processing payments"""
    # Global exception handlers will catch and format any errors
    result = await PaymentService.process_webhook(payload)
    logger.info(f"Successfully processed webhook for transaction {payload.tx_id}")
    return result


@router.get("/transaction/{tx_id}")
async def get_transaction(request: Request, tx_id: str):
    """Get transaction details by transaction ID"""
    result = await PaymentService.get_transaction_by_id(tx_id)
    
    # Handle business logic for not found case
    if result["status"] == "not_found":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result["message"])
    
    logger.info(f"Successfully retrieved transaction {tx_id}")
    return result
