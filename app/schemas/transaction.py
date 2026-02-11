from pydantic import BaseModel


# Schema for validating transaction creation requests
class TransactionCreate(BaseModel):
    tx_id: str
    amount: float
    currency: str
    sender_account: str
    receiver_account: str


# Schema for validating webhook payloads
class WebhookPayload(BaseModel):
    tx_id: str
    amount: float
    currency: str
    sender_account: str
    receiver_account: str
    description: str
