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
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Get the limiter from app state
def get_limiter(request: Request):
    """Get rate limiter from app state"""
    return request.app.state.limiter


@router.post("/webhook/payment", dependencies=[Depends(verify_hmac_signature)])
async def process_payment(request: Request, payload: WebhookPayload):
    """Main webhook endpoint for processing payments."""
    # Get limiter and apply rate limiting
    limiter = get_limiter(request)
    
    # Create a wrapper function that accepts request for rate limiting
    @limiter.limit("10/minute", key_func=get_remote_address)
    async def rate_limited_endpoint(request: Request):
        result = await PaymentService.process_webhook(payload)
        logger.info(f"Successfully processed webhook for transaction {payload.tx_id}")
        return result
    
    return await rate_limited_endpoint(request)


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
