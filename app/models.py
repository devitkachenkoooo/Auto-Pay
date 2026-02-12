from beanie import Document, Indexed
from pydantic import Field
from datetime import datetime, timezone
from typing import Optional


# Transaction model for MongoDB storage using Beanie ODM
class Transaction(Document):
    """Transaction document model for storing payment data"""

    tx_id: Indexed(str, unique=True)  # Unique index on tx_id to prevent duplicate transactions
    amount: float
    currency: Indexed(str)  # Index for currency queries
    sender_account: Indexed(str)  # Index for sender account queries
    receiver_account: Indexed(str)  # Index for receiver account queries
    status: Indexed(str) = "pending"  # Index for status queries
    timestamp: Indexed(datetime) = Field(default_factory=lambda: datetime.now(timezone.utc))  # Use factory for dynamic timing
    description: Optional[str] = None

    class Settings:
        name = "transactions"  # MongoDB collection name
