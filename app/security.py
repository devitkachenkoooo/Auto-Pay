"""
Webhook signature verification with HMAC SHA-256 and replay protection.

Fixes applied:
    - Replay protection via X-Timestamp header (rejects webhooks older than 5 minutes)
    - Signature format normalization (strips optional 'sha256=' prefix)
    - Timestamp included in HMAC payload to bind signature to time window
    - Proper use of SecurityError from exception hierarchy
"""

import hmac
import hashlib
import os
import time
from fastapi import Request, Header
from dotenv import load_dotenv
from app.core.exceptions import SecurityError
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# HMAC secret key for webhook signature verification
HMAC_SECRET = os.getenv("HMAC_SECRET_KEY")

# Maximum age for a webhook request (in seconds)
MAX_WEBHOOK_AGE_SECONDS = int(os.getenv("MAX_WEBHOOK_AGE_SECONDS", "300"))  # 5 minutes


async def verify_hmac_signature(
    request: Request,
    x_signature: str = Header(None),
    x_timestamp: str = Header(None),
):
    """
    Verify HMAC SHA-256 signature for webhook requests with replay protection.

    The expected signature is computed over: timestamp + "." + raw_body
    This binds the signature to a specific time window, preventing replay attacks.

    Args:
        request: FastAPI request object
        x_signature: X-Signature header (hex digest, optionally prefixed with 'sha256=')
        x_timestamp: X-Timestamp header (Unix timestamp as string)

    Raises:
        SecurityError: If signature is missing, invalid, or the request is too old
    """
    if not HMAC_SECRET:
        logger.error("HMAC_SECRET_KEY is not configured; denying webhook request")
        raise SecurityError(
            "Webhook verification not configured", "webhook_authentication"
        )

    # --- Validate signature header ---
    if not x_signature:
        logger.warning("Missing signature header in webhook request")
        raise SecurityError("Missing signature header", "webhook_authentication")

    # --- Replay protection: validate timestamp ---
    if not x_timestamp:
        logger.warning("Missing timestamp header in webhook request")
        raise SecurityError("Missing timestamp header", "webhook_authentication")

    try:
        request_timestamp = int(x_timestamp)
    except (ValueError, TypeError):
        raise SecurityError("Invalid timestamp format", "webhook_authentication")

    current_time = int(time.time())
    # Reject timestamps too far in the future (clock skew / replay window bypass)
    if request_timestamp > current_time + 5:
        raise SecurityError(
            "Request timestamp is in the future", "webhook_authentication"
        )

    age = current_time - request_timestamp
    if age > MAX_WEBHOOK_AGE_SECONDS:
        logger.warning(
            f"Webhook request too old: {age}s (max: {MAX_WEBHOOK_AGE_SECONDS}s)"
        )
        raise SecurityError("Request timestamp expired", "webhook_authentication")

    # --- Compute and verify HMAC signature ---
    body = getattr(request.state, "body", None)
    if body is None:
        body = await request.body()

    # The signed payload includes the timestamp to bind it to the time window
    signed_payload = f"{x_timestamp}.".encode() + body

    expected_signature = hmac.new(
        HMAC_SECRET.encode(), signed_payload, hashlib.sha256
    ).hexdigest()

    # Normalize: strip optional "sha256=" prefix from the provided signature
    provided_signature = x_signature
    if provided_signature.startswith("sha256="):
        provided_signature = provided_signature[7:]

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, provided_signature):
        logger.warning("Invalid signature in webhook request")
        raise SecurityError("Invalid signature", "webhook_authentication")

    return True
