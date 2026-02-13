"""
Pydantic response models for service layer.

Provides clean separation between service logic and HTTP concerns.
Service layer returns these models, FastAPI handles JSON serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ServiceResult(BaseModel):
    """Generic base class for all service responses."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable result message")


class PaymentResponse(ServiceResult):
    """Response model for payment webhook processing."""

    status: str = Field(
        ...,
        description="Processing status: 'processed', 'duplicate', 'accepted', 'already_processed'",
    )
    tx_id: str = Field(..., description="Transaction identifier")


class TransactionDetails(BaseModel):
    """Transaction details embedded in responses."""

    tx_id: str = Field(..., description="Transaction identifier")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    sender_account: Optional[str] = Field(None, description="Sender account")
    receiver_account: Optional[str] = Field(None, description="Receiver account")
    status: Optional[str] = Field(None, description="Transaction status")
    description: Optional[str] = Field(None, description="Transaction description")
    timestamp: Optional[datetime] = Field(None, description="Transaction timestamp")


class TransactionResponse(ServiceResult):
    """Response model for transaction retrieval."""

    status: str = Field(..., description="Retrieval status: 'found'")
    transaction: TransactionDetails = Field(..., description="Transaction details")


class WebhookResult(PaymentResponse):
    """Alias for PaymentResponse - webhook processing result."""

    pass
