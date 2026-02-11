import json
import hmac
import hashlib
import uuid
import httpx
import asyncio
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
WEBHOOK_URL = "http://localhost:8000/webhook/payment"
HMAC_SECRET = os.getenv("HMAC_SECRET_KEY")

# Debug: Check if HMAC_SECRET is loaded
if not HMAC_SECRET:
    logger.error("HMAC_SECRET_KEY not found in environment variables!")
    raise ValueError("HMAC_SECRET_KEY is required but not set")
else:
    logger.info(f"HMAC_SECRET_KEY loaded successfully (length: {len(HMAC_SECRET)})")


def generate_hmac_signature(payload: str, secret: str) -> str:
    """
    Generate HMAC SHA256 signature for the payload

    Args:
        payload: JSON string payload
        secret: HMAC secret key

    Returns:
        Hexadecimal signature
    """
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


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

    # Generate signature
    signature = generate_hmac_signature(payload_str, HMAC_SECRET)

    # Prepare headers
    headers = {"Content-Type": "application/json", "X-Signature": signature}

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


async def simulate_payment_flow():
    """
    Simulate various payment scenarios
    """
    scenarios = [
        ("Valid Transaction", generate_transaction_payload()),
        ("Duplicate Transaction", None),  # Will reuse first transaction
        ("Invalid Signature", None),  # Will use wrong signature
        ("Another Valid Transaction", generate_transaction_payload()),
    ]

    first_tx_id = None

    for scenario_name, payload in scenarios:
        logger.info(f"\n=== {scenario_name} ===")

        if scenario_name == "Duplicate Transaction" and first_tx_id:
            # Reuse the first transaction to test idempotency
            payload = generate_transaction_payload()
            payload["tx_id"] = first_tx_id

        elif scenario_name == "Invalid Signature":
            # Generate valid payload but wrong signature
            payload = generate_transaction_payload()
            payload_str = json.dumps(payload, separators=(",", ":"))
            wrong_signature = hmac.new(
                "wrong_secret".encode(), payload_str.encode(), hashlib.sha256
            ).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-Signature": wrong_signature,
            }

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        WEBHOOK_URL, data=payload_str, headers=headers, timeout=10.0
                    )
                    logger.info(f"Status: {response.status_code}")
                    logger.info(f"Response: {response.json()}")
                except Exception as e:
                    logger.error(f"Request failed: {str(e)}")

            continue

        # Send normal webhook
        response = await send_webhook(payload)

        if response and response.status_code == 200 and not first_tx_id:
            first_tx_id = payload["tx_id"]

        # Small delay between requests
        await asyncio.sleep(1)


async def main():
    """
    Main function to run the mock sender
    """
    logger.info("Starting AutoPay Mock Sender")
    logger.info(f"Target URL: {WEBHOOK_URL}")

    try:
        await simulate_payment_flow()
        logger.info("\nMock sender completed successfully")
    except KeyboardInterrupt:
        logger.info("\nMock sender interrupted")
    except Exception as e:
        logger.error(f"Mock sender failed: {str(e)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
