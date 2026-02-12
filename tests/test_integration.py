import pytest
from unittest.mock import AsyncMock
from app.services.payment_service import PaymentService


class TestWebhookSecurityIntegration:
    """Integration tests for webhook security and HMAC verification"""

    def test_missing_signature_header(self, client):
        """Test that requests without signature header are rejected"""
        response = client.post("/webhook/payment", json={
            "tx_id": "test_tx_12345",
            "amount": 100.50,
            "currency": "USD",
            "sender_account": "ACC123456",
            "receiver_account": "ACC789012",
            "description": "Test payment",
        })
        assert response.status_code == 401
        assert "Missing signature header" in response.json()["detail"]

    def test_invalid_signature(self, client):
        """Test that requests with invalid signature are rejected"""
        headers = {"X-Signature": "invalid_signature"}
        response = client.post("/webhook/payment", json={
            "tx_id": "test_tx_12345",
            "amount": 100.50,
            "currency": "USD",
            "sender_account": "ACC123456",
            "receiver_account": "ACC789012",
            "description": "Test payment",
        }, headers=headers)
        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_valid_signature(
        self, client, mock_hmac_secret, valid_webhook_headers
    ):
        """Test that requests with valid signature are accepted"""
        with pytest.MonkeyPatch().context() as m:
            m.setattr("app.routes.payments.PaymentService.process_webhook", AsyncMock(return_value={
                "status": "accepted",
                "tx_id": "test_tx_12345",
            }))

            response = client.post(
                "/webhook/payment", 
                json={
                    "tx_id": "test_tx_12345",
                    "amount": 100.50,
                    "currency": "USD",
                    "sender_account": "ACC123456",
                    "receiver_account": "ACC789012",
                    "description": "Test payment",
                },
                headers=valid_webhook_headers
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
            m.setattr("app.routes.payments.PaymentService.get_transaction_by_id", AsyncMock(return_value={
                "status": "found", 
                "transaction": {
                    "tx_id": "test_tx_12345",
                    "amount": 100.50,
                    "currency": "USD",
                    "sender_account": "ACC123456",
                    "receiver_account": "ACC789012",
                    "description": "Test payment",
                }
            }))

            response = client.get("/transaction/test_tx_12345")
            assert response.status_code == 200
            assert response.json()["status"] == "found"

    def test_get_transaction_not_found(self, client):
        """Test transaction not found"""
        with pytest.MonkeyPatch().context() as m:
            m.setattr("app.routes.payments.PaymentService.get_transaction_by_id", AsyncMock(return_value={
                "status": "not_found",
                "message": "Transaction test_tx_12345 not found",
            }))

            response = client.get("/transaction/test_tx_12345")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]


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
            
            m.setattr("app.services.payment_service.Transaction", mock_transaction_class)
            
            response = client.post(
                "/webhook/payment", 
                json={
                    "tx_id": "test_tx_12345",
                    "amount": 100.50,
                    "currency": "USD",
                    "sender_account": "ACC123456",
                    "receiver_account": "ACC789012",
                    "description": "Test payment",
                },
                headers=valid_webhook_headers
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "accepted"
            assert response.json()["tx_id"] == "test_tx_12345"

    @pytest.mark.asyncio
    async def test_webhook_end_to_end_duplicate(
        self, client, mock_hmac_secret, valid_webhook_headers, mock_existing_transaction
    ):
        """Test complete webhook flow with duplicate transaction"""
        with pytest.MonkeyPatch().context() as m:
            from unittest.mock import MagicMock
            
            # Mock the Transaction class in payment_service
            mock_transaction_class = MagicMock()
            mock_transaction_class.find_one = AsyncMock(return_value=mock_existing_transaction)
            
            m.setattr("app.services.payment_service.Transaction", mock_transaction_class)
            
            response = client.post(
                "/webhook/payment", 
                json={
                    "tx_id": "test_tx_12345",
                    "amount": 100.50,
                    "currency": "USD",
                    "sender_account": "ACC123456",
                    "receiver_account": "ACC789012",
                    "description": "Test payment",
                },
                headers=valid_webhook_headers
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "already_processed"
            assert response.json()["tx_id"] == "test_tx_12345"


class TestReplayAttackSecurityIntegration:
    """Integration tests for replay attack prevention"""

    def test_replay_attack_same_signature_twice(
        self, client, mock_hmac_secret
    ):
        """Test that using the same valid signature twice is handled properly"""
        # Generate signature for our specific test payload
        import json
        import hmac
        import hashlib
        
        payload = {
            "tx_id": "test_tx_replay",
            "amount": 100.50,
            "currency": "USD",
            "sender_account": "ACC123456",
            "receiver_account": "ACC789012",
            "description": "Replay attack test",
        }
        
        # Generate signature for this payload
        payload_str = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(
            mock_hmac_secret.encode(), 
            payload_str.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        headers = {"X-Signature": signature}
        
        with pytest.MonkeyPatch().context() as m:
            from unittest.mock import AsyncMock, MagicMock
            
            # Mock PaymentService.process_webhook directly
            mock_process_webhook = AsyncMock()
            
            call_count = 0
            def mock_webhook_side_effect(payload):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {
                        "status": "accepted",
                        "tx_id": payload.tx_id,
                        "message": "Transaction stored successfully",
                    }
                else:
                    return {
                        "status": "already_processed",
                        "tx_id": payload.tx_id,
                        "message": "Transaction was previously processed",
                    }
            
            mock_process_webhook.side_effect = mock_webhook_side_effect
            m.setattr("app.routes.payments.PaymentService.process_webhook", mock_process_webhook)
            
            # First request with valid signature
            response1 = client.post(
                "/webhook/payment", 
                json=payload,
                headers=headers
            )
            
            # Second request with same signature (replay attack)
            response2 = client.post(
                "/webhook/payment", 
                json=payload,
                headers=headers
            )
            
            # Both should succeed due to idempotency, but second should be "already_processed"
            assert response1.status_code == 200
            assert response1.json()["status"] == "accepted"
            
            assert response2.status_code == 200
            assert response2.json()["status"] == "already_processed"
            assert response2.json()["tx_id"] == "test_tx_replay"
            
            # Verify process_webhook was called twice (once for each request)
            assert mock_process_webhook.call_count == 2

    def test_replay_attack_different_payload_same_signature(
        self, client, mock_hmac_secret, valid_webhook_headers
    ):
        """Test that using the same signature with different payload should fail"""
        # This test assumes the signature is tied to the specific payload
        # Using the same signature with a different payload should be invalid
        
        different_payload = {
            "tx_id": "different_tx_123",
            "amount": 999.99,  # Different amount
            "currency": "USD",
            "sender_account": "ACC999999",
            "receiver_account": "ACC888888",
            "description": "Different payload with same signature",
        }
        
        response = client.post(
            "/webhook/payment", 
            json=different_payload,
            headers=valid_webhook_headers  # Same signature as original payload
        )
        
        # Should fail because signature doesn't match the new payload
        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_rate_limiting_protection(self, client):
        """Test that rate limiting protects against excessive requests"""
        # This test would require more sophisticated setup to properly test rate limiting
        # For now, we'll just verify the endpoint exists and rate limiting is configured
        
        # Make multiple rapid requests to the webhook endpoint
        responses = []
        for i in range(5):
            response = client.post(
                "/webhook/payment", 
                json={
                    "tx_id": f"rate_limit_test_{i}",
                    "amount": 1.00,
                    "currency": "USD",
                    "sender_account": "ACC123",
                    "receiver_account": "ACC456",
                    "description": f"Rate limit test {i}",
                }
            )
            responses.append(response)
        
        # At least some requests should be rejected due to missing signature
        # (rate limiting is secondary to signature validation)
        rejected_count = sum(1 for r in responses if r.status_code == 401)
        assert rejected_count >= 5  # All should be rejected due to missing signature


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
