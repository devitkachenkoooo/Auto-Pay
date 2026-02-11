import hmac
import hashlib
import os
from fastapi import Request, HTTPException, Header
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# HMAC secret key for webhook signature verification
HMAC_SECRET = os.getenv("HMAC_SECRET_KEY")

if not HMAC_SECRET:
    raise ValueError("HMAC_SECRET_KEY environment variable is not set")


async def verify_hmac_signature(request: Request, x_signature: str = Header(None)):
    """
    Middleware function to verify HMAC SHA256 signature for webhook requests

    Args:
        request: FastAPI request object
        x_signature: X-Signature header value

    Raises:
        HTTPException: If signature is missing or invalid
    """
    if not x_signature:
        logger.warning("Missing signature header in webhook request")
        raise HTTPException(status_code=401, detail="Missing signature header")

    # Get raw request body
    body = await request.body()

    # Calculate expected signature
    expected_signature = hmac.new(
        HMAC_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    # Compare signatures using constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, x_signature):
        logger.warning("Invalid signature in webhook request")
        raise HTTPException(status_code=401, detail="Invalid signature")

    return True
