from unittest.mock import AsyncMock


class TestAPIEndpointsIntegration:
    def test_health_check(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "active"
        assert "AutoPay AI" in response.json()["service"]

    def test_get_transaction_success(self, client, monkeypatch):
        monkeypatch.setattr(
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

    def test_get_transaction_not_found(self, client, monkeypatch):
        from app.core.exceptions import NotFoundError

        monkeypatch.setattr(
            "app.routes.payments.PaymentService.get_transaction_by_id",
            AsyncMock(side_effect=NotFoundError("Transaction", "test_tx_12345")),
        )

        response = client.get("/transaction/test_tx_12345")
        assert response.status_code == 404
        response_data = response.json()
        assert response_data["error"] == "NotFoundError"
        assert "not found" in response_data["message"]
