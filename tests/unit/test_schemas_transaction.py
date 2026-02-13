import pytest
from pydantic import ValidationError

from app.schemas.transaction import WebhookPayload


@pytest.mark.parametrize(
    "payload_key,expected_loc,expected_type",
    [
        ("empty_tx_id", ("tx_id",), "string_too_short"),
        ("negative_amount", ("amount",), "greater_than"),
        ("zero_amount", ("amount",), "greater_than"),
        ("empty_sender", ("sender_account",), "string_too_short"),
        ("empty_receiver", ("receiver_account",), "string_too_short"),
        ("invalid_amount_type", ("amount",), "decimal_parsing"),
        ("too_high_amount", ("amount",), "less_than_equal"),
        ("too_many_decimals", ("amount",), "decimal_max_places"),
        ("invalid_tx_id_format", ("tx_id",), "string_pattern_mismatch"),
        ("invalid_currency_format", ("currency",), "string_pattern_mismatch"),
        ("invalid_tx_id_chars", ("tx_id",), "string_pattern_mismatch"),
        ("long_description", ("description",), "string_too_long"),
    ],
)
def test_webhook_payload_validation_errors(
    invalid_payloads, payload_key, expected_loc, expected_type
):
    with pytest.raises(ValidationError) as exc_info:
        WebhookPayload(**invalid_payloads[payload_key])

    errors = exc_info.value.errors()
    assert any(error["loc"] == expected_loc for error in errors)
    assert any(error["type"] == expected_type for error in errors)


def test_same_accounts_rejected(invalid_payloads):
    with pytest.raises(ValidationError):
        WebhookPayload(**invalid_payloads["same_accounts"])


def test_description_sanitization():
    """Test that description sanitization removes prohibited characters and handles empty results"""
    # Test sanitization of prohibited characters
    malicious_payload = {
        "tx_id": "test_tx_123",
        "amount": "100.50",
        "currency": "USD",
        "sender_account": "ACC123",
        "receiver_account": "ACC456",
        "description": "Test <script>alert(\"XSS\")</script> with 'quotes' & ampersands; end.",
    }

    payload = WebhookPayload(**malicious_payload)

    # Assert prohibited characters are removed
    expected_description = "Test scriptalert(XSS)/script with quotes  ampersands end."
    assert payload.description == expected_description

    # Test that description with only prohibited characters returns None
    empty_description_payload = malicious_payload.copy()
    empty_description_payload["description"] = "<>\"';&"

    payload_empty = WebhookPayload(**empty_description_payload)
    assert payload_empty.description is None
