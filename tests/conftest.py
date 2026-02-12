import pytest
import tenacity
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.models import Transaction
from app.services.payment_service import PaymentService
from app.schemas.transaction import WebhookPayload

# Test data
VALID_PAYLOAD = {
    "tx_id": "test_tx_12345",
    "amount": 100.50,
    "currency": "USD",
    "sender_account": "ACC123456",
    "receiver_account": "ACC789012",
    "description": "Test payment",
}

HMAC_SECRET = "test_secret_key"


@pytest.fixture
def client():
    """FastAPI TestClient fixture"""
    return TestClient(app)


@pytest.fixture
def mock_transaction():
    """Mock app.models.Transaction with autospec=True"""
    with patch("app.models.Transaction", autospec=True) as mock:
        yield mock


@pytest.fixture
def mock_payment_service():
    """Mock app.services.payment_service.PaymentService with autospec=True"""
    with patch("app.services.payment_service.PaymentService", autospec=True) as mock:
        yield mock


@pytest.fixture
def mock_db_find():
    """Mock Transaction.find_one using AsyncMock for async calls"""
    with patch("app.models.Transaction.find_one", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_db_insert():
    """Mock Transaction.insert using AsyncMock for async calls"""
    with patch("app.models.Transaction.insert", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_transaction_service():
    """Mock Transaction in payment_service module where it's used"""
    with patch("app.services.payment_service.Transaction", autospec=True) as mock:
        yield mock


# Webhook payload helpers
def create_webhook_payload(tx_id="test_tx_12345", amount=100.50, currency="USD", 
                          sender_account="ACC123456", receiver_account="ACC789012", 
                          description="Test payment"):
    """Create webhook payload with customizable parameters"""
    return {
        "tx_id": tx_id,
        "amount": amount,
        "currency": currency,
        "sender_account": sender_account,
        "receiver_account": receiver_account,
        "description": description,
    }


def create_invalid_webhook_payloads():
    """Create various invalid webhook payloads for testing"""
    return {
        "negative_amount": create_webhook_payload(amount=-100.50, tx_id="neg_amount"),
        "zero_amount": create_webhook_payload(amount=0.00, tx_id="zero_amount"),
        "empty_tx_id": create_webhook_payload(tx_id="", amount=100.50),
        "empty_sender": create_webhook_payload(sender_account="", tx_id="empty_sender"),
        "empty_receiver": create_webhook_payload(receiver_account="", tx_id="empty_receiver"),
        "same_accounts": create_webhook_payload(sender_account="ACC123", receiver_account="ACC123", tx_id="same_acc"),
    }


@pytest.fixture
def webhook_payload():
    """Create a valid WebhookPayload instance"""
    return WebhookPayload(**VALID_PAYLOAD)


@pytest.fixture
def webhook_payloads():
    """Fixture providing various webhook payloads for testing"""
    return {
        "valid": create_webhook_payload(),
        "invalid": create_invalid_webhook_payloads()
    }


@pytest.fixture
def mock_populated_transaction(mock_transaction_data):
    """Create a mock transaction automatically populated with data"""
    mock_transaction = AsyncMock()
    mock_transaction.__dict__.update(mock_transaction_data)
    return mock_transaction


@pytest.fixture
def mock_existing_transaction():
    """Create a mock existing transaction object"""
    mock_tx = AsyncMock()
    mock_tx.tx_id = VALID_PAYLOAD["tx_id"]
    mock_tx.amount = VALID_PAYLOAD["amount"]
    mock_tx.currency = VALID_PAYLOAD["currency"]
    mock_tx.sender_account = VALID_PAYLOAD["sender_account"]
    mock_tx.receiver_account = VALID_PAYLOAD["receiver_account"]
    mock_tx.status = "success"
    mock_tx.description = VALID_PAYLOAD["description"]
    mock_tx.timestamp = "2024-01-01T00:00:00Z"
    return mock_tx


@pytest.fixture
def mock_hmac_secret():
    """Mock HMAC_SECRET for signature testing"""
    with patch("app.security.HMAC_SECRET", HMAC_SECRET):
        yield HMAC_SECRET


def generate_signature(payload: dict, secret: str) -> str:
    """Generate HMAC SHA256 signature for testing"""
    import hmac
    import hashlib
    import json
    payload_str = json.dumps(payload, separators=(",", ":"))
    return hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def valid_signature():
    """Generate valid signature for VALID_PAYLOAD"""
    return generate_signature(VALID_PAYLOAD, HMAC_SECRET)


@pytest.fixture
def valid_webhook_headers(valid_signature):
    """Headers with valid HMAC signature"""
    return {"X-Signature": valid_signature}


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for test isolation"""
    import os
    from unittest.mock import patch
    
    original_env = os.environ.copy()
    test_env = {
        "GEMINI_API_KEY": "test_api_key",
        "HMAC_SECRET_KEY": "test_secret_key",
        "MONGO_URL": "mongodb://localhost:27017/test"
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        yield test_env
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_ai_client():
    """Mock app.services.ai_service.genai.Client with autospec=True"""
    with patch("app.services.ai_service.genai.Client", autospec=True) as mock:
        yield mock


# Retry patching standardization
@pytest.fixture
def mock_zero_wait_retry():
    """Standard fixture for patching retry mechanisms to zero wait time"""
    with patch("tenacity.wait_exponential", side_effect=lambda: tenacity.wait_fixed(0)):
        yield


@pytest.fixture
def mock_transaction_data():
    """Generic transaction data for AI/Unit tests"""
    return {
        "tx_id": "test_tx_12345",
        "amount": 100.50,
        "currency": "USD",
        "sender_account": "ACC123456",
        "receiver_account": "ACC789012",
        "status": "success",
        "description": "Test transaction",
        "timestamp": None
    }
