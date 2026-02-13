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
