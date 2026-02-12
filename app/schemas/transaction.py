from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal
import re


class TransactionCreate(BaseModel):
    """Schema for validating transaction creation requests with enhanced validation"""
    
    tx_id: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="Unique transaction identifier",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    
    amount: Decimal = Field(
        ..., 
        gt=0,
        decimal_places=2,
        max_digits=15,
        description="Transaction amount (must be positive)"
    )
    
    currency: str = Field(
        ..., 
        min_length=3,
        max_length=3,
        description="3-letter currency code (e.g., USD)",
        pattern=r"^[A-Z]{3}$"
    )
    
    sender_account: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="Sender account identifier",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    
    receiver_account: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="Receiver account identifier",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )

    @field_validator('receiver_account')
    @classmethod
    def different_accounts(cls, v, info):
        """Ensure sender and receiver accounts are different"""
        if 'sender_account' in info.data and v == info.data['sender_account']:
            raise ValueError('Sender and receiver accounts must be different')
        return v


class WebhookPayload(BaseModel):
    """Schema for validating webhook payloads with comprehensive validation"""
    
    tx_id: str = Field(
        ..., 
        min_length=1,
        max_length=100,
        description="Unique transaction identifier",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    
    amount: Decimal = Field(
        ..., 
        gt=0,
        decimal_places=2,
        max_digits=15,
        description="Transaction amount (must be positive)"
    )
    
    currency: str = Field(
        ..., 
        min_length=3,
        max_length=3,
        description="3-letter currency code (e.g., USD)",
        pattern=r"^[A-Z]{3}$"
    )
    
    sender_account: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="Sender account identifier",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    
    receiver_account: str = Field(
        ..., 
        min_length=1,
        max_length=50,
        description="Receiver account identifier",
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    
    description: Optional[str] = Field(
        None, 
        max_length=500,
        description="Optional transaction description"
    )

    @field_validator('receiver_account')
    @classmethod
    def different_accounts(cls, v, info):
        """Ensure sender and receiver accounts are different"""
        if 'sender_account' in info.data and v == info.data['sender_account']:
            raise ValueError('Sender and receiver accounts must be different')
        return v

    @field_validator('description')
    def validate_description(cls, v):
        """Validate description content if provided"""
        if v is not None:
            # Remove any potentially harmful content
            v = re.sub(r'[<>"\']', '', v)
            if len(v.strip()) == 0:
                return None
        return v
