from beanie import Document
from datetime import datetime, timezone
from typing import Optional


# Transaction model for MongoDB storage using Beanie ODM
class Transaction(Document):
    """Transaction document model for storing payment data"""

    tx_id: str
    amount: float
    currency: str
    sender_account: str
    receiver_account: str
    status: str = "pending"
    timestamp: datetime = datetime.now(timezone.utc)
    description: Optional[str] = None

    class Settings:
        name = "transactions"  # MongoDB collection name
