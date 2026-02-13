import pytest
import tenacity
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.transaction import WebhookPayload
import os

# Test data
VALID_PAYLOAD = {
    "tx_id": "test_tx_12345",
    "amount": "100.50",  # String to match Decimal field
    "currency": "USD",
    "sender_account": "ACC123456",
    "receiver_account": "ACC789012",
    "description": "Test payment",
}

HMAC_SECRET = "test_secret_key"


@pytest.fixture
def mock_db_init():
    """Mock database initialization to prevent CollectionWasNotInitialized errors"""
    with patch("app.database.init_beanie", new_callable=AsyncMock) as mock_init:
        mock_init.return_value = None
        yield mock_init


@pytest.fixture
def client(mock_db_init):
    """FastAPI TestClient fixture with mocked database"""
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
def create_webhook_payload(
    tx_id="test_tx_12345",
    amount="100.50",
    currency="USD",
    sender_account="ACC123456",
    receiver_account="ACC789012",
    description="Test payment",
):
    """Create webhook payload with customizable parameters"""
    return {
        "tx_id": tx_id,
        "amount": amount,  # String to match Decimal field
        "currency": currency,
        "sender_account": sender_account,
        "receiver_account": receiver_account,
        "description": description,
    }


def create_invalid_webhook_payloads():
    """Create various invalid webhook payloads for testing"""
    return {
        "negative_amount": create_webhook_payload(amount="-100.50", tx_id="neg_amount"),
        "zero_amount": create_webhook_payload(amount="0.00", tx_id="zero_amount"),
        "empty_tx_id": create_webhook_payload(tx_id="", amount="100.50"),
        "empty_sender": create_webhook_payload(sender_account="", tx_id="empty_sender"),
        "empty_receiver": create_webhook_payload(
            receiver_account="", tx_id="empty_receiver"
        ),
        "same_accounts": create_webhook_payload(
            sender_account="ACC123", receiver_account="ACC123", tx_id="same_acc"
        ),
        "invalid_amount_type": create_webhook_payload(amount="not_a_number"),
        "too_high_amount": create_webhook_payload(amount="1000001.00"),
        "too_many_decimals": create_webhook_payload(amount="100.555"),
        "invalid_tx_id_format": create_webhook_payload(tx_id="invalid id! @#$"),
        "invalid_currency_format": create_webhook_payload(currency="usd"),
        "invalid_tx_id_chars": create_webhook_payload(tx_id="tx@123!"),
        "long_description": create_webhook_payload(description="a" * 501),
    }


@pytest.fixture
def webhook_payload():
    """Create a valid WebhookPayload instance"""
    return WebhookPayload(**VALID_PAYLOAD)


@pytest.fixture
def valid_payload():
    return dict(VALID_PAYLOAD)


@pytest.fixture
def invalid_payloads():
    return create_invalid_webhook_payloads()


@pytest.fixture
def webhook_payloads():
    """Fixture providing various webhook payloads for testing"""
    return {
        "valid": create_webhook_payload(),
        "invalid": create_invalid_webhook_payloads(),
    }


@pytest.fixture
def mock_populated_transaction():
    """Create a mock transaction automatically populated with data"""
    from decimal import Decimal
    from datetime import datetime

    mock_transaction = AsyncMock()
    # Set all attributes directly with proper types
    mock_transaction.tx_id = "test_tx_12345"
    mock_transaction.amount = Decimal("100.50")  # Convert to Decimal
    mock_transaction.currency = "USD"
    mock_transaction.sender_account = "ACC123456"
    mock_transaction.receiver_account = "ACC789012"
    mock_transaction.status = "success"
    mock_transaction.description = "Test payment"
    mock_transaction.timestamp = datetime(2024, 1, 1, 0, 0, 0)  # Use datetime object
    return mock_transaction


@pytest.fixture
def mock_existing_transaction():
    """Create a mock existing transaction object"""
    from decimal import Decimal
    from datetime import datetime

    mock_tx = AsyncMock()
    mock_tx.tx_id = VALID_PAYLOAD["tx_id"]
    mock_tx.amount = Decimal(VALID_PAYLOAD["amount"])  # Convert to Decimal
    mock_tx.currency = VALID_PAYLOAD["currency"]
    mock_tx.sender_account = VALID_PAYLOAD["sender_account"]
    mock_tx.receiver_account = VALID_PAYLOAD["receiver_account"]
    mock_tx.status = "success"
    mock_tx.description = VALID_PAYLOAD["description"]
    mock_tx.timestamp = datetime(2024, 1, 1, 0, 0, 0)  # Use datetime object
    return mock_tx


@pytest.fixture
def mock_hmac_secret():
    """Mock HMAC_SECRET for signature testing"""
    with patch("app.security.HMAC_SECRET", HMAC_SECRET):
        yield HMAC_SECRET


def generate_signature(payload: dict, secret: str, timestamp: int = None) -> str:
    """Generate HMAC SHA256 signature for testing"""
    import hmac
    import hashlib
    import json
    import time

    if timestamp is None:
        timestamp = int(time.time())

    payload_str = json.dumps(payload, separators=(",", ":"))
    # Signature is computed over timestamp + "." + payload
    sign_data = f"{timestamp}.{payload_str}"
    return hmac.new(
        secret.encode(), sign_data.encode(), hashlib.sha256
    ).hexdigest(), timestamp


@pytest.fixture
def valid_signature():
    """Generate valid signature and timestamp for VALID_PAYLOAD"""
    signature, timestamp = generate_signature(VALID_PAYLOAD, HMAC_SECRET)
    return signature, timestamp


@pytest.fixture
def valid_webhook_headers(valid_signature):
    """Headers with valid HMAC signature and timestamp"""
    signature, timestamp = valid_signature
    return {"X-Signature": signature, "X-Timestamp": str(timestamp)}


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for test isolation"""
    from unittest.mock import patch

    original_env = os.environ.copy()
    test_env = {
        "GEMINI_API_KEY": "test_api_key",
        "HMAC_SECRET_KEY": "test_secret_key",
        "MONGO_URL": "mongodb://localhost:27017/test",
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
    with (
        patch("tenacity.wait_exponential", return_value=tenacity.wait_fixed(0)),
        patch(
            "tenacity.stop_after_attempt", return_value=tenacity.stop_after_attempt(3)
        ),
    ):
        yield


@pytest.fixture
def mock_transaction_data():
    """Generic transaction data for AI/Unit tests"""
    return {
        "tx_id": "test_tx_12345",
        "amount": 100.50,  # Use float for AI service calculations
        "currency": "USD",
        "sender_account": "ACC123456",
        "receiver_account": "ACC789012",
        "status": "success",
        "description": "Test transaction",
        "timestamp": None,
    }
