from fastapi import APIRouter, Depends, HTTPException, Request
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
@limiter.limit("10/minute")
async def process_payment(request: Request, payload: WebhookPayload):
    """Main webhook endpoint for processing payments"""
    try:
        result = await PaymentService.process_webhook(payload)
        return result
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/transaction/{tx_id}")
@limiter.limit("30/minute")
async def get_transaction(request: Request, tx_id: str):
    """Get transaction details by transaction ID"""
    try:
        result = await PaymentService.get_transaction_by_id(tx_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transaction retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
