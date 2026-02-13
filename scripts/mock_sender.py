import json
import hmac
import hashlib
import uuid
import httpx
import asyncio
from dotenv import load_dotenv
import os
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
WEBHOOK_URL = "http://localhost:8001/payments/webhook"
HMAC_SECRET = os.getenv("HMAC_SECRET_KEY")

# Debug: Check if HMAC_SECRET is loaded
if not HMAC_SECRET:
    logger.error("HMAC_SECRET_KEY not found in environment variables!")
    raise ValueError("HMAC_SECRET_KEY is required but not set")
else:
    logger.info(f"HMAC_SECRET_KEY loaded successfully (length: {len(HMAC_SECRET)})")


def generate_hmac(timestamp: int, payload: str, secret: str) -> str:
    """
    Generate HMAC SHA256 signature for the payload

    Args:
        timestamp: Unix timestamp
        payload: JSON string payload
        secret: HMAC secret key

    Returns:
        Hexadecimal signature
    """
    signed_payload = f"{timestamp}.{payload}"
    return hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()


def generate_transaction_payload() -> dict:
    """
    Generate a realistic transaction payload

    Returns:
        Dictionary with transaction data
    """
    return {
        "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
        "amount": round(
            float(uuid.uuid4().int % 10000) / 100, 2
        ),  # Random amount 0.01-99.99
        "currency": "USD",
        "sender_account": f"ACC{uuid.uuid4().hex[:8].upper()}",
        "receiver_account": f"ACC{uuid.uuid4().hex[:8].upper()}",
        "description": f"Payment for order #{uuid.uuid4().hex[:10].upper()}",
    }


async def send_webhook(payload: dict):
    """
    Send webhook with HMAC signature

    Args:
        payload: Transaction payload dictionary
    """
    # Convert to JSON string
    payload_str = json.dumps(payload, separators=(",", ":"))

    # Get current timestamp
    timestamp = int(time.time())

    # Generate signature
    signature = generate_hmac(timestamp, payload_str, HMAC_SECRET)

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": str(timestamp),
        "X-Signature": signature
    }

    # Send request
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                WEBHOOK_URL, data=payload_str, headers=headers, timeout=10.0
            )

            logger.info(f"Status: {response.status_code}")
            logger.info(f"Response: {response.json()}")

            return response

        except httpx.RequestError as e:
            logger.error(f"Request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return None


async def run_test_scenarios():
    """
    Run specific advanced testing scenarios
    """
    test_cases = [
        {
            "name": "Case 1: Success Path",
            "payload": generate_transaction_payload(),
            "expected_status": 200,
            "description": "Valid data, valid signature"
        },
        {
            "name": "Case 2: Security Breach (Invalid Signature)",
            "payload": generate_transaction_payload(),
            "expected_status": 401,
            "description": "Valid payload but with hardcoded 'fake_sig'",
            "force_signature": "fake_sig"
        },
        {
            "name": "Case 3: XSS Attack (Sanitization Test)",
            "payload": {
                "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
                "amount": 100.00,
                "currency": "USD",
                "sender_account": f"ACC{uuid.uuid4().hex[:8].upper()}",
                "receiver_account": f"ACC{uuid.uuid4().hex[:8].upper()}",
                "description": "<script>alert('xss')</script> Test payment"
            },
            "expected_status": 200,
            "description": "Description containing script tags"
        },
        {
            "name": "Case 4: Business Rule Violation",
            "payload": {
                "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
                "amount": 50.00,
                "currency": "USD",
                "sender_account": "SAME_ACC_123",
                "receiver_account": "SAME_ACC_123",
                "description": "Same sender and receiver test"
            },
            "expected_status": 422,
            "description": "sender_account equals receiver_account"
        },
        {
            "name": "Case 5: Precision Test",
            "payload": {
                "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
                "amount": 100.555,
                "currency": "USD",
                "sender_account": f"ACC{uuid.uuid4().hex[:8].upper()}",
                "receiver_account": f"ACC{uuid.uuid4().hex[:8].upper()}",
                "description": "Test with 3 decimal places"
            },
            "expected_status": 422,
            "description": "Amount with 3 decimal places"
        }
    ]

    for case in test_cases:
        logger.info(f"\n=== {case['name']} ===")
        logger.info(f"Description: {case['description']}")

        payload = case["payload"]
        expected_status = case["expected_status"]

        # Send request
        if "force_signature" in case:
            # Special case for invalid signature
            payload_str = json.dumps(payload, separators=(",", ":"))
            timestamp = int(time.time())
            headers = {
                "Content-Type": "application/json",
                "X-Timestamp": str(timestamp),
                "X-Signature": case["force_signature"]
            }

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        WEBHOOK_URL, data=payload_str, headers=headers, timeout=10.0
                    )
                    status_code = response.status_code
                    response_data = response.json()
                except Exception as e:
                    logger.error(f"Request failed: {str(e)}")
                    status_code = None
                    response_data = None
        else:
            response = await send_webhook(payload)
            if response:
                status_code = response.status_code
                response_data = response.json()
            else:
                status_code = None
                response_data = None

        # Check result
        if status_code == expected_status:
            logger.info("PASS")
        else:
            logger.info("FAIL")
            logger.info(f"Expected status: {expected_status}, Got: {status_code}")

        if response_data:
            logger.info(f"Response: {response_data}")

        # Small delay between requests
        await asyncio.sleep(1)


async def main():
    """
    Main function to run the mock sender
    """
    logger.info("Starting AutoPay Mock Sender")
    logger.info(f"Target URL: {WEBHOOK_URL}")

    try:
        await run_test_scenarios()
        logger.info("\nMock sender completed successfully")
    except KeyboardInterrupt:
        logger.info("\nMock sender interrupted")
    except Exception as e:
        logger.error(f"Mock sender failed: {str(e)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
