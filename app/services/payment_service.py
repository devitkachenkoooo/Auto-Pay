"""
Payment processing service layer.

Fixes applied:
    - Removed logging.basicConfig() (clobbers root logger config)
    - DatabaseError no longer wraps raw str(e) which could contain connection strings
    - get_transaction_by_id raises NotFoundError instead of returning a status dict
      (lets the exception hierarchy handle HTTP semantics cleanly)
"""

from app.models import Transaction
from app.schemas.transaction import WebhookPayload
from app.schemas.responses import (
    PaymentResponse,
    TransactionResponse,
    TransactionDetails,
)
from app.core.exceptions import (
    PaymentValidationError,
    IdempotencyError,
    DatabaseError,
    NotFoundError,
)
import logging
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)


class PaymentService:
    """Service layer for handling payment processing logic"""

    @staticmethod
    async def process_webhook(payload: WebhookPayload) -> PaymentResponse:
        """
        Process incoming webhook payload with idempotency protection.

        Args:
            payload: Validated webhook payload

        Returns:
            PaymentResponse with processing status and details

        Raises:
            PaymentValidationError: If payment data fails validation
            IdempotencyError: If transaction already exists
            DatabaseError: If database operations fail
        """
        # Defensive validation (business rules beyond Pydantic)
        PaymentService._validate_payment_data(payload)

        try:
            # Check for existing transaction (idempotency)
            existing_tx = await Transaction.find_one({"tx_id": payload.tx_id})

            if existing_tx:
                logger.info(f"Transaction {payload.tx_id} already processed")
                return PaymentResponse(
                    success=True,
                    message="Transaction was previously processed",
                    status="duplicate",
                    tx_id=payload.tx_id,
                )

            # Create new transaction record
            new_transaction = Transaction(
                tx_id=payload.tx_id,
                amount=float(payload.amount),
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
                # Race condition: another process inserted the same tx_id
                logger.info(f"Duplicate transaction detected: {payload.tx_id}")
                raise IdempotencyError(payload.tx_id)

            logger.info(f"Successfully processed transaction {payload.tx_id}")
            return PaymentResponse(
                success=True,
                message="Transaction stored successfully",
                status="processed",
                tx_id=payload.tx_id,
            )

        except (IdempotencyError, PaymentValidationError):
            # Re-raise domain exceptions as-is
            raise
        except DuplicateKeyError:
            raise IdempotencyError(payload.tx_id)
        except Exception:
            # Log the full error internally but don't expose it to the client
            logger.error(
                f"Database error processing transaction {payload.tx_id}", exc_info=True
            )
            raise DatabaseError(
                "Failed to process transaction",
                operation="insert_transaction",
            )

    @staticmethod
    async def get_transaction_by_id(tx_id: str) -> TransactionResponse:
        """
        Retrieve transaction details by ID.

        Args:
            tx_id: Transaction identifier

        Returns:
            TransactionResponse with transaction details

        Raises:
            NotFoundError: If the transaction does not exist
            DatabaseError: If database operations fail
        """
        try:
            transaction = await Transaction.find_one({"tx_id": tx_id})

            if not transaction:
                raise NotFoundError("Transaction", tx_id)

            transaction_details = TransactionDetails(
                tx_id=transaction.tx_id,
                amount=transaction.amount,
                currency=transaction.currency,
                sender_account=transaction.sender_account,
                receiver_account=transaction.receiver_account,
                status=transaction.status,
                description=transaction.description,
                timestamp=transaction.timestamp,
            )

            return TransactionResponse(
                success=True,
                message="Transaction found successfully",
                status="found",
                transaction=transaction_details,
            )

        except NotFoundError:
            raise
        except Exception:
            logger.error(
                f"Database error retrieving transaction {tx_id}", exc_info=True
            )
            raise DatabaseError(
                "Failed to retrieve transaction",
                operation="find_transaction",
            )

    @staticmethod
    def _validate_payment_data(payload: WebhookPayload) -> None:
        """
        Validate payment data with business rules beyond Pydantic schema.

        Args:
            payload: Webhook payload to validate

        Raises:
            PaymentValidationError: If validation fails
        """
        # Validate transaction ID
        if not payload.tx_id or not payload.tx_id.strip():
            raise PaymentValidationError(
                "Transaction ID cannot be empty",
                "tx_id",
            )

        # Validate amount
        if payload.amount <= 0:
            raise PaymentValidationError(
                "Transaction amount must be positive",
                "amount",
            )

        # Validate currency
        if not payload.currency or not payload.currency.strip():
            raise PaymentValidationError(
                "Currency cannot be empty",
                "currency",
            )

        # Validate account numbers
        if not payload.sender_account or not payload.sender_account.strip():
            raise PaymentValidationError(
                "Sender account cannot be empty",
                "sender_account",
            )

        if not payload.receiver_account or not payload.receiver_account.strip():
            raise PaymentValidationError(
                "Receiver account cannot be empty",
                "receiver_account",
            )

        # Business rule: sender and receiver should be different
        if payload.sender_account == payload.receiver_account:
            raise PaymentValidationError(
                "Sender and receiver accounts must be different",
                "accounts",
            )
