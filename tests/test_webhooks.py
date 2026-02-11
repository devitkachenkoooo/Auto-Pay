import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.transaction import WebhookPayload
from app.services.payment_service import PaymentService
from app.models import Transaction
import hmac
import hashlib
import json

client = TestClient(app)

# Test data
VALID_PAYLOAD = {
    "tx_id": "test_tx_12345",
    "amount": 100.50,
    "currency": "USD",
    "sender_account": "ACC123456",
    "receiver_account": "ACC789012",
    "description": "Test payment",
}

HMAC_SECRET = "test_secret_key"


def generate_signature(payload: dict, secret: str) -> str:
    """Generate HMAC SHA256 signature for testing"""
    payload_str = json.dumps(payload, separators=(",", ":"))
    return hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()


class TestWebhookSecurity:
    """Test webhook security and HMAC verification"""

    def test_missing_signature_header(self):
        """Test that requests without signature header are rejected"""
        response = client.post("/webhook/payment", json=VALID_PAYLOAD)
        assert response.status_code == 401
        assert "Missing signature header" in response.json()["detail"]

    def test_invalid_signature(self):
        """Test that requests with invalid signature are rejected"""
        headers = {"X-Signature": "invalid_signature"}
        response = client.post("/webhook/payment", json=VALID_PAYLOAD, headers=headers)
        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_valid_signature(self):
        """Test that requests with valid signature are accepted"""
        signature = generate_signature(VALID_PAYLOAD, HMAC_SECRET)
        headers = {"X-Signature": signature}

        with patch("app.security.HMAC_SECRET", HMAC_SECRET):
            with patch.object(
                PaymentService, "process_webhook", new_callable=AsyncMock
            ) as mock_process:
                mock_process.return_value = {
                    "status": "accepted",
                    "tx_id": VALID_PAYLOAD["tx_id"],
                }

                response = client.post(
                    "/webhook/payment", json=VALID_PAYLOAD, headers=headers
                )
                assert response.status_code == 200
                mock_process.assert_called_once()


class TestPaymentService:
    """Test payment service business logic"""

    @pytest.mark.asyncio
    async def test_process_new_transaction(self):
        """Test processing a new transaction"""
        payload = WebhookPayload(**VALID_PAYLOAD)

        # Mock Transaction where it's used, not where it's defined
        with patch(
            "app.services.payment_service.Transaction"
        ) as mock_transaction_class:
            # Mock find_one class method
            mock_transaction_class.find_one = AsyncMock(return_value=None)

            # Mock constructor to return our mock instance
            mock_transaction_instance = AsyncMock()
            mock_transaction_instance.insert = AsyncMock()
            mock_transaction_class.return_value = mock_transaction_instance

            result = await PaymentService.process_webhook(payload)

            assert result["status"] == "accepted"
            assert result["tx_id"] == VALID_PAYLOAD["tx_id"]
            mock_transaction_class.find_one.assert_called_once_with(
                {"tx_id": VALID_PAYLOAD["tx_id"]}
            )
            mock_transaction_instance.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_duplicate_transaction(self):
        """Test processing a duplicate transaction (idempotency)"""
        payload = WebhookPayload(**VALID_PAYLOAD)

        # Create a mock transaction object instead of real Transaction
        mock_existing_tx = AsyncMock()
        mock_existing_tx.tx_id = VALID_PAYLOAD["tx_id"]
        mock_existing_tx.amount = VALID_PAYLOAD["amount"]
        mock_existing_tx.currency = VALID_PAYLOAD["currency"]
        mock_existing_tx.sender_account = VALID_PAYLOAD["sender_account"]
        mock_existing_tx.receiver_account = VALID_PAYLOAD["receiver_account"]
        mock_existing_tx.status = "success"
        mock_existing_tx.description = VALID_PAYLOAD["description"]

        with patch.object(Transaction, "find_one", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_existing_tx  # Existing transaction found

            result = await PaymentService.process_webhook(payload)

            assert result["status"] == "already_processed"
            assert result["tx_id"] == VALID_PAYLOAD["tx_id"]
            mock_find.assert_called_once_with({"tx_id": VALID_PAYLOAD["tx_id"]})

    @pytest.mark.asyncio
    async def test_get_existing_transaction(self):
        """Test retrieving an existing transaction"""
        # Create a mock transaction object
        mock_existing_tx = AsyncMock()
        mock_existing_tx.tx_id = VALID_PAYLOAD["tx_id"]
        mock_existing_tx.amount = VALID_PAYLOAD["amount"]
        mock_existing_tx.currency = VALID_PAYLOAD["currency"]
        mock_existing_tx.sender_account = VALID_PAYLOAD["sender_account"]
        mock_existing_tx.receiver_account = VALID_PAYLOAD["receiver_account"]
        mock_existing_tx.status = "success"
        mock_existing_tx.description = VALID_PAYLOAD["description"]
        mock_existing_tx.timestamp = "2024-01-01T00:00:00Z"

        with patch.object(Transaction, "find_one", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_existing_tx

            result = await PaymentService.get_transaction_by_id(VALID_PAYLOAD["tx_id"])

            assert result["status"] == "found"
            assert result["transaction"]["tx_id"] == VALID_PAYLOAD["tx_id"]
            mock_find.assert_called_once_with({"tx_id": VALID_PAYLOAD["tx_id"]})

    @pytest.mark.asyncio
    async def test_get_nonexistent_transaction(self):
        """Test retrieving a non-existent transaction"""
        with patch.object(Transaction, "find_one", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            result = await PaymentService.get_transaction_by_id("nonexistent_tx")

            assert result["status"] == "not_found"
            assert "not found" in result["message"]
            mock_find.assert_called_once_with({"tx_id": "nonexistent_tx"})


class TestAPIEndpoints:
    """Test API endpoints"""

    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "active"
        assert "AutoPay AI" in response.json()["service"]

    def test_get_transaction_success(self):
        """Test successful transaction retrieval"""
        with patch.object(
            PaymentService, "get_transaction_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {"status": "found", "transaction": VALID_PAYLOAD}

            response = client.get(f"/transaction/{VALID_PAYLOAD['tx_id']}")
            assert response.status_code == 200
            assert response.json()["status"] == "found"

    def test_get_transaction_not_found(self):
        """Test transaction not found"""
        with patch.object(
            PaymentService, "get_transaction_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {
                "status": "not_found",
                "message": f"Transaction {VALID_PAYLOAD['tx_id']} not found",
            }

            response = client.get(f"/transaction/{VALID_PAYLOAD['tx_id']}")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test handling of database errors"""
        payload = WebhookPayload(**VALID_PAYLOAD)

        with patch.object(Transaction, "find_one", new_callable=AsyncMock) as mock_find:
            mock_find.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception) as exc_info:
                await PaymentService.process_webhook(payload)

            assert "Failed to process transaction" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
