import pytest
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


@pytest.fixture
def webhook_payload():
    """Create a valid WebhookPayload instance"""
    return WebhookPayload(**VALID_PAYLOAD)


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
def mock_ai_client():
    """Mock app.services.ai_service.genai.Client with autospec=True"""
    with patch("app.services.ai_service.genai.Client", autospec=True) as mock:
        yield mock


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
