import json
import hmac
import hashlib
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


@pytest.fixture
def payments_router():
    from app.routes.payments import router

    return router


def create_rate_limit_test_app(router):
    app = FastAPI()

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["5/second"],
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(router)

    return app


def test_webhook_rate_limiting_5_per_second(payments_router, mock_hmac_secret):
    test_app = create_rate_limit_test_app(payments_router)
    client = TestClient(test_app)

    payload = {
        "tx_id": "rate_limit_test_tx",
        "amount": "100.00",
        "currency": "USD",
        "sender_account": "test_user",
        "receiver_account": "test_receiver",
        "description": "rate limit test",
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = "1700000000"
    signed_payload = f"{timestamp}.".encode() + payload_bytes

    signature = hmac.new(
        mock_hmac_secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    with patch("app.routes.payments.get_remote_address", return_value="9.9.9.9"), patch(
        "time.time", return_value=1700000000.0
    ), patch("app.services.payment_service.PaymentService.process_webhook") as mock_process:
        from app.schemas.responses import PaymentResponse

        mock_process.return_value = PaymentResponse(
            success=True,
            message="processed",
            status="processed",
            tx_id="rate_limit_test_tx",
        )

        status_codes = []
        for _ in range(6):
            response = client.post(
                "/webhook",
                data=payload_bytes,
                headers={
                    "X-Signature": signature,
                    "X-Timestamp": timestamp,
                    "Content-Type": "application/json",
                },
            )
            status_codes.append(response.status_code)

    assert status_codes.count(200) == 5
    assert status_codes.count(429) == 1
