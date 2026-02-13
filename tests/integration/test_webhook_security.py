import time
from unittest.mock import AsyncMock


class TestWebhookSecurityIntegration:
    def test_missing_signature_header(self, client, valid_payload):
        response = client.post(
            "/webhook",
            json={
                **valid_payload,
                "amount": 100.50,
            },
        )

        assert response.status_code == 401
        response_data = response.json()
        assert response_data["error"] == "SecurityError"
        assert "Missing signature header" in response_data["message"]

    def test_invalid_signature(self, client, valid_payload):
        headers = {
            "X-Signature": "invalid_signature",
            "X-Timestamp": str(int(time.time())),
        }

        response = client.post(
            "/webhook",
            json={
                **valid_payload,
                "amount": 100.50,
            },
            headers=headers,
        )

        assert response.status_code == 401
        response_data = response.json()
        assert response_data["error"] == "SecurityError"
        assert "Invalid signature" in response_data["message"]

    def test_valid_signature(
        self,
        client,
        mock_hmac_secret,
        valid_payload,
        valid_webhook_headers,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.routes.payments.PaymentService.process_webhook",
            AsyncMock(
                return_value={"status": "processed", "tx_id": valid_payload["tx_id"]}
            ),
        )

        response = client.post(
            "/webhook", json=valid_payload, headers=valid_webhook_headers
        )
        assert response.status_code == 200
