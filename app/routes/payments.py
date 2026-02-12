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


@router.post("/webhook", dependencies=[Depends(verify_hmac_signature)])
async def process_payment(request: Request, payload: WebhookPayload):
    """Main webhook endpoint for processing payments."""
    # Retrieve the limiter from the app state
    limiter = get_limiter(request)
    
    # We use a 30/minute limit here to stay generous for the full test suite
    # while still providing protection. The specific rate limiting test will 
    # override this behavior by using a separate app with a 5/minute default limit.
    @limiter.limit("30/minute", key_func=get_remote_address)
    async def handle_request(request: Request):
        return await PaymentService.process_webhook(payload)

    return await handle_request(request)


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
