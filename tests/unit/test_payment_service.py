import pytest
from unittest.mock import AsyncMock

from app.services.payment_service import PaymentService
from app.core.exceptions import DatabaseError


class TestPaymentServiceUnit:
    @pytest.mark.asyncio
    async def test_process_new_transaction(
        self, webhook_payload, mock_transaction_service
    ):
        mock_transaction_service.find_one = AsyncMock(return_value=None)

        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock()
        mock_transaction_service.return_value = mock_transaction_instance

        result = await PaymentService.process_webhook(webhook_payload)

        assert result.status == "processed"
        assert result.tx_id == webhook_payload.tx_id
        mock_transaction_service.find_one.assert_called_once_with(
            {"tx_id": webhook_payload.tx_id}
        )
        mock_transaction_instance.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_duplicate_transaction(
        self, webhook_payload, mock_existing_transaction, mock_db_find
    ):
        mock_db_find.return_value = mock_existing_transaction

        result = await PaymentService.process_webhook(webhook_payload)

        assert result.status == "duplicate"
        assert result.tx_id == webhook_payload.tx_id
        mock_db_find.assert_called_once_with({"tx_id": webhook_payload.tx_id})

    @pytest.mark.asyncio
    async def test_get_existing_transaction(
        self, mock_existing_transaction, mock_db_find
    ):
        mock_db_find.return_value = mock_existing_transaction

        result = await PaymentService.get_transaction_by_id(
            mock_existing_transaction.tx_id
        )

        assert result.status == "found"
        assert result.transaction.tx_id == mock_existing_transaction.tx_id
        mock_db_find.assert_called_once_with({"tx_id": mock_existing_transaction.tx_id})

    @pytest.mark.asyncio
    async def test_get_nonexistent_transaction(self, mock_db_find):
        mock_db_find.return_value = None

        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError) as exc_info:
            await PaymentService.get_transaction_by_id("nonexistent_tx")

        assert "Transaction not found" in str(exc_info.value)
        assert exc_info.value.identifier == "nonexistent_tx"
        mock_db_find.assert_called_once_with({"tx_id": "nonexistent_tx"})


class TestErrorHandlingUnit:
    @pytest.mark.asyncio
    async def test_database_error_handling(self, webhook_payload, mock_db_find):
        mock_db_find.side_effect = Exception("Database connection failed")

        with pytest.raises(DatabaseError) as exc_info:
            await PaymentService.process_webhook(webhook_payload)

        assert "Failed to process transaction" in str(exc_info.value)
        assert exc_info.value.operation == "insert_transaction"

    @pytest.mark.asyncio
    async def test_database_timeout_handling(self, webhook_payload, mock_db_find):
        mock_db_find.side_effect = Exception("Database Timeout")

        with pytest.raises(DatabaseError) as exc_info:
            await PaymentService.process_webhook(webhook_payload)

        assert "Failed to process transaction" in str(exc_info.value)
        assert exc_info.value.operation == "insert_transaction"
        mock_db_find.assert_called_once_with({"tx_id": webhook_payload.tx_id})


class TestDataIntegrityUnit:
    @pytest.mark.asyncio
    async def test_corrupted_transaction_data_missing_fields(self, mock_db_find):
        corrupted_transaction = AsyncMock()
        corrupted_transaction.tx_id = "test_tx_12345"
        corrupted_transaction.amount = None
        corrupted_transaction.currency = None
        corrupted_transaction.sender_account = None
        corrupted_transaction.receiver_account = None
        corrupted_transaction.status = None
        corrupted_transaction.description = None
        corrupted_transaction.timestamp = None

        mock_db_find.return_value = corrupted_transaction

        with pytest.raises(DatabaseError) as exc_info:
            await PaymentService.get_transaction_by_id("test_tx_12345")

        assert "Failed to retrieve transaction" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transaction_with_incomplete_data(
        self, mock_db_find, mock_populated_transaction
    ):
        incomplete_transaction = mock_populated_transaction
        incomplete_transaction.tx_id = "test_tx_partial"
        incomplete_transaction.amount = 100.50
        incomplete_transaction.currency = "USD"
        incomplete_transaction.sender_account = "ACC123"
        incomplete_transaction.receiver_account = None
        incomplete_transaction.status = "success"
        incomplete_transaction.description = "Partial transaction"
        incomplete_transaction.timestamp = None

        mock_db_find.return_value = incomplete_transaction

        result = await PaymentService.get_transaction_by_id("test_tx_partial")

        assert result.status == "found"
        assert result.transaction.tx_id == "test_tx_partial"
        assert result.transaction.amount == 100.50
        assert result.transaction.receiver_account is None

    @pytest.mark.asyncio
    async def test_database_insert_failure(
        self, webhook_payload, mock_transaction_service
    ):
        mock_transaction_service.find_one = AsyncMock(return_value=None)

        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock(
            side_effect=Exception("Insert operation failed")
        )
        mock_transaction_service.return_value = mock_transaction_instance

        with pytest.raises(DatabaseError) as exc_info:
            await PaymentService.process_webhook(webhook_payload)

        assert "Failed to process transaction" in str(exc_info.value)
        mock_transaction_instance.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_transaction_corrupted_db_response(self, mock_db_find):
        mock_db_find.return_value = {"tx_id": "test_tx_corrupted", "amount": 100.50}

        with pytest.raises(DatabaseError) as exc_info:
            await PaymentService.get_transaction_by_id("test_tx_corrupted")

        assert "Failed to retrieve transaction" in str(exc_info.value)
