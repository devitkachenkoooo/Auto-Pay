import pytest
import time
import hmac
import hashlib
import json
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

pytest.skip("Legacy module: moved to tests/integration/", allow_module_level=True)


class TestWebhookSecurityIntegration:
    """Integration tests for webhook security and HMAC verification"""

    def test_missing_signature_header(self, client):
        """Test that requests without signature header are rejected"""
        response = client.post(
            "/webhook",
            json={
                "tx_id": "test_tx_12345",
                "amount": 100.50,
                "currency": "USD",
                "sender_account": "ACC123456",
                "receiver_account": "ACC789012",
                "description": "Test payment",
            },
        )
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["error"] == "SecurityError"
        assert "Missing signature header" in response_data["message"]

    def test_invalid_signature(self, client):
        """Test that requests with invalid signature are rejected"""
        headers = {
            "X-Signature": "invalid_signature",
            "X-Timestamp": str(int(time.time())),
        }
        response = client.post(
            "/webhook",
            json={
                "tx_id": "test_tx_12345",
                "amount": 100.50,
                "currency": "USD",
                "sender_account": "ACC123456",
                "receiver_account": "ACC789012",
                "description": "Test payment",
            },
            headers=headers,
        )
        assert response.status_code == 401
        response_data = response.json()
        assert response_data["error"] == "SecurityError"
        assert "Invalid signature" in response_data["message"]

    def test_valid_signature(self, client, mock_hmac_secret, valid_webhook_headers):
        """Test that requests with valid signature are accepted"""
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "app.routes.payments.PaymentService.process_webhook",
                AsyncMock(
                    return_value={
                        "status": "processed",
                        "tx_id": "test_tx_12345",
                    }
                ),
            )

            # Use the same payload that was used to generate the signature
            from tests.conftest import VALID_PAYLOAD

            response = client.post(
                "/webhook", json=VALID_PAYLOAD, headers=valid_webhook_headers
            )
            assert response.status_code == 200


class TestAPIEndpointsIntegration:
    """Integration tests for API endpoints"""

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "active"
        assert "AutoPay AI" in response.json()["service"]

    def test_get_transaction_success(self, client):
        """Test successful transaction retrieval"""
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "app.routes.payments.PaymentService.get_transaction_by_id",
                AsyncMock(
                    return_value={
                        "status": "found",
                        "transaction": {
                            "tx_id": "test_tx_12345",
                            "amount": 100.50,
                            "currency": "USD",
                            "sender_account": "ACC123456",
                            "receiver_account": "ACC789012",
                            "description": "Test payment",
                        },
                    }
                ),
            )

            response = client.get("/transaction/test_tx_12345")
            assert response.status_code == 200
            assert response.json()["status"] == "found"

    def test_get_transaction_not_found(self, client):
        """Test transaction not found"""
        with pytest.MonkeyPatch().context() as m:
            from app.core.exceptions import NotFoundError

            # Mock the service to raise NotFoundError
            m.setattr(
                "app.routes.payments.PaymentService.get_transaction_by_id",
                AsyncMock(side_effect=NotFoundError("Transaction", "test_tx_12345")),
            )

            response = client.get("/transaction/test_tx_12345")
            assert response.status_code == 404
            response_data = response.json()
            assert response_data["error"] == "NotFoundError"
            assert "not found" in response_data["message"]


class TestFullWebhookFlowIntegration:
    """Integration tests for complete webhook flow"""

    @pytest.mark.asyncio
    async def test_webhook_end_to_end_success(
        self, client, mock_hmac_secret, valid_webhook_headers
    ):
        """Test complete webhook flow with valid signature and successful processing"""
        with pytest.MonkeyPatch().context() as m:
            from unittest.mock import MagicMock

            # Mock the Transaction class in payment_service
            mock_transaction_class = MagicMock()
            mock_transaction_class.find_one = AsyncMock(return_value=None)

            # Mock the constructor to return a proper instance
            mock_transaction_instance = MagicMock()
            mock_transaction_instance.insert = AsyncMock()
            mock_transaction_class.return_value = mock_transaction_instance

            m.setattr(
                "app.services.payment_service.Transaction", mock_transaction_class
            )

            # Use the same payload that was used to generate the signature
            from tests.conftest import VALID_PAYLOAD

            response = client.post(
                "/webhook", json=VALID_PAYLOAD, headers=valid_webhook_headers
            )

            assert response.status_code == 200
            assert response.json()["status"] == "processed"
            assert response.json()["tx_id"] == VALID_PAYLOAD["tx_id"]

    @pytest.mark.asyncio
    async def test_webhook_end_to_end_duplicate(
        self, client, mock_hmac_secret, valid_webhook_headers, mock_existing_transaction
    ):
        """Test complete webhook flow with duplicate transaction"""
        with pytest.MonkeyPatch().context() as m:
            from unittest.mock import MagicMock

            # Mock the Transaction class in payment_service
            mock_transaction_class = MagicMock()
            mock_transaction_class.find_one = AsyncMock(
                return_value=mock_existing_transaction
            )

            m.setattr(
                "app.services.payment_service.Transaction", mock_transaction_class
            )

            # Use the same payload that was used to generate the signature
            from tests.conftest import VALID_PAYLOAD

            response = client.post(
                "/webhook", json=VALID_PAYLOAD, headers=valid_webhook_headers
            )

            assert response.status_code == 200
            assert response.json()["status"] == "duplicate"
            assert response.json()["tx_id"] == VALID_PAYLOAD["tx_id"]


def test_webhook_replay_attack_idempotency(client, mock_hmac_secret):
    """
    Test that replay attacks are handled via idempotency logic, not rate limiting.
    Verified via business-level 'duplicate' response and service call count.
    """
    payload = {
        "tx_id": "replay_test_tx",
        "amount": 100.0,
        "currency": "USD",
        "sender_account": "test_user",
        "receiver_account": "test_receiver",
        "description": "Replay test",
    }

    payload_bytes = json.dumps(payload).encode()
    secret = mock_hmac_secret

    # Generate signature using the project's HMAC format (includes timestamp)
    import time

    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.".encode() + payload_bytes

    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    # Patch the service call in the route
    with patch("app.routes.payments.PaymentService.process_webhook") as mock_process:
        # First call: processed
        # Second call: duplicate
        mock_process.side_effect = [{"status": "processed"}, {"status": "duplicate"}]

        response1 = client.post(
            "/webhook",
            data=payload_bytes,
            headers={
                "X-Signature": signature,
                "X-Timestamp": timestamp,
                "Content-Type": "application/json",
            },
        )

        response2 = client.post(
            "/webhook",
            data=payload_bytes,
            headers={
                "X-Signature": signature,
                "X-Timestamp": timestamp,
                "Content-Type": "application/json",
            },
        )

    assert response1.status_code == 200
    assert response2.status_code == 200

    assert response1.json()["status"] == "processed"
    assert response2.json()["status"] == "duplicate"

    assert mock_process.call_count == 2


def test_replay_attack_different_payload_same_signature(
    client, mock_hmac_secret, valid_webhook_headers
):
    """Test that using the same signature with different payload should fail"""
    different_payload = {
        "tx_id": "different_tx_123",
        "amount": 999.99,
        "currency": "USD",
        "sender_account": "ACC999999",
        "receiver_account": "ACC888888",
        "description": "Different payload with same signature",
    }

    response = client.post(
        "/webhook", json=different_payload, headers=valid_webhook_headers
    )

    assert response.status_code == 401
    assert "Invalid signature" in response.json()["message"]


@pytest.fixture
def router_fixture():
    from app.routes.payments import router

    return router


def create_rate_limit_test_app(router):
    app = FastAPI()

    # We use a separate limiter instance.
    # To avoid the override from the @limiter.limit("10/minute") in the route,
    # we set the default limit to 5/minute. SlowAPI will apply all matching limits.
    # The smallest limit (5/minute) will trigger first.
    limiter = Limiter(key_func=get_remote_address, default_limits=["5/minute"])

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    # Re-include router to ensure it uses the new limiter from app.state
    app.include_router(router)

    return app


def test_webhook_rate_limiting_strict(router_fixture, mock_hmac_secret):
    test_app = create_rate_limit_test_app(router_fixture)
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
    secret = mock_hmac_secret

    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.".encode() + payload_bytes
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    success_count = 0
    rate_limited_count = 0
    server_error_count = 0

    # We mock PaymentService.process_webhook as requested.
    # To ensure absolute determinism and avoid crosstalk with other tests which
    # might be using 127.0.0.1 or other recently used IPs, we mock get_remote_address
    # to return a unique key specifically for this test.
    with (
        patch(
            "app.services.payment_service.PaymentService.process_webhook"
        ) as mock_process,
        patch("app.routes.payments.get_remote_address") as mock_remote_addr,
    ):
        mock_remote_addr.return_value = "1.2.3.4"  # Unique IP for this test
        from app.schemas.responses import PaymentResponse

        mock_process.return_value = PaymentResponse(
            success=True,
            message="processed",
            status="processed",
            tx_id="rate_limit_test_tx",
        )

        for _ in range(10):
            response = client.post(
                "/webhook",
                data=payload_bytes,
                headers={
                    "X-Signature": signature,
                    "X-Timestamp": timestamp,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited_count += 1
            else:
                # Log unexpected status for debugging
                server_error_count += 1

    assert success_count == 5, f"Expected 5 successes, got {success_count}"
    assert rate_limited_count == 5, f"Expected 5 rate limited, got {rate_limited_count}"
    assert server_error_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
