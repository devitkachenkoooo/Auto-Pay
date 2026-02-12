"""
Payment webhook and transaction routes.

Fixes applied:
    - Removed unused local Limiter instance (dead code)
    - Removed lazy 'from fastapi import HTTPException' inside function body
    - get_transaction no longer interprets service dict; 
      service raises NotFoundError which the handler catches automatically
"""

from fastapi import APIRouter, Depends, Request
from app.schemas.transaction import WebhookPayload
from app.security import verify_hmac_signature
from app.services.payment_service import PaymentService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook/payment", dependencies=[Depends(verify_hmac_signature)])
async def process_payment(request: Request, payload: WebhookPayload):
    """Main webhook endpoint for processing payments."""
    result = await PaymentService.process_webhook(payload)
    logger.info(f"Successfully processed webhook for transaction {payload.tx_id}")
    return result


@router.get("/transaction/{tx_id}")
async def get_transaction(request: Request, tx_id: str):
    """
    Get transaction details by transaction ID.
    
    Raises NotFoundError (404) automatically via exception handler
    if the transaction does not exist.
    """
    result = await PaymentService.get_transaction_by_id(tx_id)
    logger.info(f"Successfully retrieved transaction {tx_id}")
    return result
