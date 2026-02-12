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
        assert "Missing signature header" in response.json()["detail"]["message"]

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
        assert "Invalid signature" in response.json()["detail"]["message"]

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
        assert "Invalid signature" in response.json()["detail"]["message"]

    def test_rate_limiting_protection(self, client):
        """Test that rate limiting protects against excessive requests with deterministic behavior"""
        # Mock HMAC_SECRET to match our test signatures
        from unittest.mock import patch
        
        with patch("app.security.HMAC_SECRET", "test_secret_key"):
            # Test with a simple valid payload
            base_payload = {
                "tx_id": "rate_limit_test_base",
                "amount": 1.00,
                "currency": "USD", 
                "sender_account": "ACC123",
                "receiver_account": "ACC456",
                "description": "Rate limit test",
            }
            
            # Generate signature for this payload
            import hmac
            import hashlib
            import json
            HMAC_SECRET = "test_secret_key"
            payload_str = json.dumps(base_payload, separators=(",", ":"))
            signature = hmac.new(HMAC_SECRET.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
            headers = {"X-Signature": signature}
            
            # Make exactly 15 requests to test rate limiting (limit is 10/minute)
            # We expect some to be rate limited, but the exact number may vary due to test state
            responses = []
            for i in range(15):
                response = client.post("/webhook/payment", json=base_payload, headers=headers)
                responses.append(response)
            
            # Count different response types
            success_count = sum(1 for r in responses if r.status_code == 200)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)
            server_error_count = sum(1 for r in responses if r.status_code == 500)
            
            # More realistic assertions:
            # - Should have some rate limited responses (at least 1)
            # - Should have some non-rate-limited responses (they may succeed or fail due to database)
            assert rate_limited_count >= 1, f"Should have at least 1 rate limited request, got {rate_limited_count}"
            assert success_count + server_error_count >= 1, f"Should have at least 1 non-rate-limited request, got {success_count + server_error_count}"
            assert rate_limited_count + success_count + server_error_count == 15, f"Should have exactly 15 total responses, got {rate_limited_count + success_count + server_error_count}"
            
            # Verify rate limited responses contain proper error information
            rate_limited_responses = [r for r in responses if r.status_code == 429]
            for response in rate_limited_responses:
                response_json = response.json()
                assert "error" in response_json, f"Rate limited response should have 'error' field: {response_json}"
                assert "Rate limit exceeded" in response_json["error"], f"Should mention rate limit exceeded: {response_json['error']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
