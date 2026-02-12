from typing import Dict, Any
from app.models import Transaction
from app.schemas.transaction import WebhookPayload
from app.core.exceptions import PaymentValidationError, IdempotencyError, DatabaseError
import logging
from pymongo.errors import DuplicateKeyError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaymentService:
    """Service layer for handling payment processing logic"""

    @staticmethod
    async def process_webhook(payload: WebhookPayload) -> Dict[str, Any]:
        """
        Process incoming webhook payload with idempotency protection

        Args:
            payload: Validated webhook payload

        Returns:
            Dict with processing status and details

        Raises:
            PaymentValidationError: If payment data fails validation
            IdempotencyError: If transaction already exists
            DatabaseError: If database operations fail
        """
        # Defensive validation
        PaymentService._validate_payment_data(payload)
        
        try:
            # Check for existing transaction (idempotency)
            existing_tx = await Transaction.find_one({"tx_id": payload.tx_id})

            if existing_tx:
                logger.info(f"Transaction {payload.tx_id} already processed")
                return {
                    "status": "already_processed",
                    "tx_id": payload.tx_id,
                    "message": "Transaction was previously processed",
                }

            # Create new transaction record
            new_transaction = Transaction(
                tx_id=payload.tx_id,
                amount=payload.amount,
                currency=payload.currency,
                sender_account=payload.sender_account,
                receiver_account=payload.receiver_account,
                status="success",
                description=payload.description,
            )

            # Save to database with atomic operation
            try:
                await new_transaction.insert()
            except DuplicateKeyError:
                # Handle race condition where another process inserted the same tx_id
                logger.info(f"Duplicate transaction detected: {payload.tx_id}")
                raise IdempotencyError(payload.tx_id)

            logger.info(f"Successfully processed transaction {payload.tx_id}")
            return {
                "status": "accepted",
                "tx_id": payload.tx_id,
                "message": "Transaction stored successfully",
            }

        except DuplicateKeyError:
            # Re-raise as IdempotencyError for consistent handling
            raise IdempotencyError(payload.tx_id)
        except IdempotencyError:
            # Re-raise IdempotencyError
            raise
        except Exception as e:
            logger.error(f"Database error processing transaction {payload.tx_id}: {str(e)}")
            raise DatabaseError(f"Failed to process transaction: {str(e)}", "insert_transaction")

    @staticmethod
    async def get_transaction_by_id(tx_id: str) -> Dict[str, Any]:
        """
        Retrieve transaction details by ID

        Args:
            tx_id: Transaction identifier

        Returns:
            Transaction details or error message
        """
        try:
            transaction = await Transaction.find_one({"tx_id": tx_id})

            if not transaction:
                return {
                    "status": "not_found",
                    "message": f"Transaction {tx_id} not found",
                }

            return {
                "status": "found",
                "transaction": {
                    "tx_id": transaction.tx_id,
                    "amount": transaction.amount,
                    "currency": transaction.currency,
                    "sender_account": transaction.sender_account,
                    "receiver_account": transaction.receiver_account,
                    "status": transaction.status,
                    "description": transaction.description,
                    "timestamp": transaction.timestamp,
                },
            }

        except Exception as e:
            logger.error(f"Database error retrieving transaction {tx_id}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve transaction: {str(e)}", "find_transaction")
    
    @staticmethod
    def _validate_payment_data(payload: WebhookPayload) -> None:
        """
        Validate payment data with business rules
        
        Args:
            payload: Webhook payload to validate
            
        Raises:
            PaymentValidationError: If validation fails
        """
        # Validate transaction ID
        if not payload.tx_id or not payload.tx_id.strip():
            raise PaymentValidationError(
                "Transaction ID cannot be empty", 
                "tx_id"
            )
        
        # Validate amount
        if payload.amount <= 0:
            raise PaymentValidationError(
                "Transaction amount must be positive", 
                "amount"
            )
        
        # Validate currency
        if not payload.currency or not payload.currency.strip():
            raise PaymentValidationError(
                "Currency cannot be empty", 
                "currency"
            )
        
        # Validate account numbers
        if not payload.sender_account or not payload.sender_account.strip():
            raise PaymentValidationError(
                "Sender account cannot be empty", 
                "sender_account"
            )
        
        if not payload.receiver_account or not payload.receiver_account.strip():
            raise PaymentValidationError(
                "Receiver account cannot be empty", 
                "receiver_account"
            )
        
        # Additional business rule: sender and receiver should be different
        if payload.sender_account == payload.receiver_account:
            raise PaymentValidationError(
                "Sender and receiver accounts must be different", 
                "accounts"
            )
