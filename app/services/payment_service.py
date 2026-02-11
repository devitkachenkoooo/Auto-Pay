from typing import Dict, Any
from app.models import Transaction
from app.schemas.transaction import WebhookPayload
import logging

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
            Exception: If database operations fail
        """
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

            # Save to database
            await new_transaction.insert()

            logger.info(f"Successfully processed transaction {payload.tx_id}")
            return {
                "status": "accepted",
                "tx_id": payload.tx_id,
                "message": "Transaction stored successfully",
            }

        except Exception as e:
            logger.error(f"Error processing transaction {payload.tx_id}: {str(e)}")
            raise Exception(f"Failed to process transaction: {str(e)}")

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
            logger.error(f"Error retrieving transaction {tx_id}: {str(e)}")
            raise Exception(f"Failed to retrieve transaction: {str(e)}")
