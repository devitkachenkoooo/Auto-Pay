import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.payment_service import PaymentService


class TestPaymentServiceUnit:
    """Unit tests for PaymentService business logic"""

    @pytest.mark.asyncio
    async def test_process_new_transaction(
        self, webhook_payload, mock_transaction_service
    ):
        """Test processing a new transaction"""
        # Mock find_one class method
        mock_transaction_service.find_one = AsyncMock(return_value=None)
        
        # Mock constructor to return our mock instance
        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock()
        mock_transaction_service.return_value = mock_transaction_instance

        result = await PaymentService.process_webhook(webhook_payload)

        assert result["status"] == "accepted"
        assert result["tx_id"] == webhook_payload.tx_id
        mock_transaction_service.find_one.assert_called_once_with(
            {"tx_id": webhook_payload.tx_id}
        )
        mock_transaction_instance.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_duplicate_transaction(
        self, webhook_payload, mock_existing_transaction, mock_db_find
    ):
        """Test processing a duplicate transaction (idempotency)"""
        mock_db_find.return_value = mock_existing_transaction

        result = await PaymentService.process_webhook(webhook_payload)

        assert result["status"] == "already_processed"
        assert result["tx_id"] == webhook_payload.tx_id
        mock_db_find.assert_called_once_with({"tx_id": webhook_payload.tx_id})

    @pytest.mark.asyncio
    async def test_get_existing_transaction(
        self, mock_existing_transaction, mock_db_find
    ):
        """Test retrieving an existing transaction"""
        mock_db_find.return_value = mock_existing_transaction

        result = await PaymentService.get_transaction_by_id(mock_existing_transaction.tx_id)

        assert result["status"] == "found"
        assert result["transaction"]["tx_id"] == mock_existing_transaction.tx_id
        mock_db_find.assert_called_once_with({"tx_id": mock_existing_transaction.tx_id})

    @pytest.mark.asyncio
    async def test_get_nonexistent_transaction(self, mock_db_find):
        """Test retrieving a non-existent transaction"""
        mock_db_find.return_value = None

        result = await PaymentService.get_transaction_by_id("nonexistent_tx")

        assert result["status"] == "not_found"
        assert "not found" in result["message"]
        mock_db_find.assert_called_once_with({"tx_id": "nonexistent_tx"})


class TestErrorHandlingUnit:
    """Unit tests for error handling scenarios"""

    @pytest.mark.asyncio
    async def test_database_error_handling(self, webhook_payload, mock_db_find):
        """Test handling of database errors"""
        mock_db_find.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception) as exc_info:
            await PaymentService.process_webhook(webhook_payload)

        assert "Failed to process transaction" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_database_timeout_handling(self, webhook_payload, mock_db_find):
        """Test handling of database timeout scenarios"""
        mock_db_find.side_effect = Exception("Database Timeout")

        with pytest.raises(Exception) as exc_info:
            await PaymentService.process_webhook(webhook_payload)

        assert "Failed to process transaction" in str(exc_info.value)
        assert "Database Timeout" in str(exc_info.value)
        mock_db_find.assert_called_once_with({"tx_id": webhook_payload.tx_id})


class TestEdgeCasesUnit:
    """Unit tests for edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_empty_transaction_id(self, mock_transaction_service):
        """Test processing with empty tx_id"""
        from app.schemas.transaction import WebhookPayload
        
        # Create payload with empty tx_id
        empty_payload = WebhookPayload(
            tx_id="",
            amount=100.50,
            currency="USD",
            sender_account="ACC123456",
            receiver_account="ACC789012",
            description="Test payment"
        )
        
        mock_transaction_service.find_one = AsyncMock(return_value=None)
        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock()
        mock_transaction_service.return_value = mock_transaction_instance

        result = await PaymentService.process_webhook(empty_payload)

        assert result["status"] == "accepted"
        assert result["tx_id"] == ""
        mock_transaction_service.find_one.assert_called_once_with({"tx_id": ""})

    @pytest.mark.asyncio
    async def test_negative_amount(self, mock_transaction_service):
        """Test processing with negative amount"""
        from app.schemas.transaction import WebhookPayload
        
        # Create payload with negative amount
        negative_payload = WebhookPayload(
            tx_id="test_tx_negative",
            amount=-100.50,
            currency="USD",
            sender_account="ACC123456",
            receiver_account="ACC789012",
            description="Test payment with negative amount"
        )
        
        mock_transaction_service.find_one = AsyncMock(return_value=None)
        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock()
        mock_transaction_service.return_value = mock_transaction_instance

        result = await PaymentService.process_webhook(negative_payload)

        assert result["status"] == "accepted"
        assert result["tx_id"] == "test_tx_negative"
        mock_transaction_instance.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_amount(self, mock_transaction_service):
        """Test processing with zero amount"""
        from app.schemas.transaction import WebhookPayload
        
        # Create payload with zero amount
        zero_payload = WebhookPayload(
            tx_id="test_tx_zero",
            amount=0.00,
            currency="USD",
            sender_account="ACC123456",
            receiver_account="ACC789012",
            description="Test payment with zero amount"
        )
        
        mock_transaction_service.find_one = AsyncMock(return_value=None)
        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock()
        mock_transaction_service.return_value = mock_transaction_instance

        result = await PaymentService.process_webhook(zero_payload)

        assert result["status"] == "accepted"
        assert result["tx_id"] == "test_tx_zero"

    @pytest.mark.asyncio
    async def test_empty_accounts(self, mock_transaction_service):
        """Test processing with empty account numbers"""
        from app.schemas.transaction import WebhookPayload
        
        # Create payload with empty account numbers
        empty_accounts_payload = WebhookPayload(
            tx_id="test_tx_empty_accounts",
            amount=100.50,
            currency="USD",
            sender_account="",
            receiver_account="",
            description="Test payment with empty accounts"
        )
        
        mock_transaction_service.find_one = AsyncMock(return_value=None)
        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock()
        mock_transaction_service.return_value = mock_transaction_instance

        result = await PaymentService.process_webhook(empty_accounts_payload)

        assert result["status"] == "accepted"
        assert result["tx_id"] == "test_tx_empty_accounts"


class TestDataIntegrityUnit:
    """Unit tests for data integrity and corruption scenarios"""

    @pytest.mark.asyncio
    async def test_corrupted_transaction_data_missing_fields(self, mock_db_find):
        """Test handling of corrupted transaction data with missing fields"""
        # Create a mock transaction with missing critical fields
        corrupted_transaction = MagicMock()
        corrupted_transaction.tx_id = "test_tx_123"
        corrupted_transaction.amount = None  # Missing amount
        corrupted_transaction.currency = None  # Missing currency
        corrupted_transaction.sender_account = None  # Missing sender
        corrupted_transaction.receiver_account = None  # Missing receiver
        corrupted_transaction.status = None  # Missing status
        corrupted_transaction.description = None  # Missing description
        corrupted_transaction.timestamp = None
        
        mock_db_find.return_value = corrupted_transaction
        
        result = await PaymentService.get_transaction_by_id("test_tx_123")
        
        assert result["status"] == "found"
        # Should handle None values gracefully
        assert result["transaction"]["tx_id"] == "test_tx_123"
        assert result["transaction"]["amount"] is None
        assert result["transaction"]["currency"] is None

    @pytest.mark.asyncio
    async def test_transaction_with_incomplete_data(self, mock_db_find):
        """Test handling of transaction with incomplete data"""
        # Create a mock transaction with some fields missing
        incomplete_transaction = MagicMock()
        incomplete_transaction.tx_id = "test_tx_partial"
        incomplete_transaction.amount = 100.50
        incomplete_transaction.currency = "USD"
        incomplete_transaction.sender_account = "ACC123"
        # Missing receiver_account
        incomplete_transaction.receiver_account = None
        incomplete_transaction.status = "success"
        incomplete_transaction.description = "Partial transaction"
        incomplete_transaction.timestamp = None
        
        mock_db_find.return_value = incomplete_transaction
        
        result = await PaymentService.get_transaction_by_id("test_tx_partial")
        
        assert result["status"] == "found"
        assert result["transaction"]["tx_id"] == "test_tx_partial"
        assert result["transaction"]["amount"] == 100.50
        assert result["transaction"]["receiver_account"] is None

    @pytest.mark.asyncio
    async def test_database_insert_failure(self, webhook_payload, mock_transaction_service):
        """Test handling of database insert operation failure"""
        mock_transaction_service.find_one = AsyncMock(return_value=None)
        
        # Mock constructor to return instance that fails on insert
        mock_transaction_instance = AsyncMock()
        mock_transaction_instance.insert = AsyncMock(side_effect=Exception("Insert operation failed"))
        mock_transaction_service.return_value = mock_transaction_instance

        with pytest.raises(Exception) as exc_info:
            await PaymentService.process_webhook(webhook_payload)

        assert "Failed to process transaction" in str(exc_info.value)
        assert "Insert operation failed" in str(exc_info.value)
        mock_transaction_instance.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_transaction_corrupted_db_response(self, mock_db_find):
        """Test handling when database returns corrupted/incomplete data"""
        # Mock database returning a response that's not a proper transaction object
        corrupted_response = {
            "tx_id": "test_tx_corrupted",
            "amount": 100.50,
            # Missing other required fields
        }
        
        mock_db_find.return_value = corrupted_response
        
        # This should cause an Exception when trying to access missing fields
        with pytest.raises(Exception) as exc_info:
            await PaymentService.get_transaction_by_id("test_tx_corrupted")
        
        assert "Failed to retrieve transaction" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
