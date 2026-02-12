import json
import hmac
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFullWebhookFlowIntegration:
    @pytest.mark.asyncio
    async def test_webhook_end_to_end_success(self, client, mock_hmac_secret, valid_webhook_headers, valid_payload, monkeypatch):
        mock_transaction_class = MagicMock()
        mock_transaction_class.find_one = AsyncMock(return_value=None)

        mock_transaction_instance = MagicMock()
        mock_transaction_instance.insert = AsyncMock()
        mock_transaction_class.return_value = mock_transaction_instance

        monkeypatch.setattr("app.services.payment_service.Transaction", mock_transaction_class)

        response = client.post("/webhook", json=valid_payload, headers=valid_webhook_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        assert response.json()["tx_id"] == valid_payload["tx_id"]

    @pytest.mark.asyncio
    async def test_webhook_end_to_end_duplicate(self, client, mock_hmac_secret, valid_webhook_headers, valid_payload, mock_existing_transaction, monkeypatch):
        mock_transaction_class = MagicMock()
        mock_transaction_class.find_one = AsyncMock(return_value=mock_existing_transaction)

        monkeypatch.setattr("app.services.payment_service.Transaction", mock_transaction_class)

        response = client.post("/webhook", json=valid_payload, headers=valid_webhook_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "duplicate"
        assert response.json()["tx_id"] == valid_payload["tx_id"]


def test_webhook_replay_attack_idempotency_calls_service_twice(client, mock_hmac_secret):
    payload = {
        "tx_id": "replay_test_tx",
        "amount": 100.0,
        "currency": "USD",
        "sender_account": "test_user",
        "receiver_account": "test_receiver",
        "description": "Replay test",
    }

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.".encode() + payload_bytes

    signature = hmac.new(
        mock_hmac_secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    with patch("app.routes.payments.get_remote_address", return_value="7.7.7.7"), patch(
        "app.routes.payments.PaymentService.process_webhook"
    ) as mock_process:
        mock_process.side_effect = [
            {"status": "processed"},
            {"status": "duplicate"},
        ]

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


def test_replay_attack_different_payload_same_signature_fails(client, mock_hmac_secret, valid_webhook_headers):
    different_payload = {
        "tx_id": "different_tx_123",
        "amount": 999.99,
        "currency": "USD",
        "sender_account": "ACC999999",
        "receiver_account": "ACC888888",
        "description": "Different payload with same signature",
    }

    response = client.post("/webhook", json=different_payload, headers=valid_webhook_headers)

    assert response.status_code == 401
    assert "Invalid signature" in response.json()["message"]
