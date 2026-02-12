import pytest
from unittest.mock import MagicMock, patch
import tenacity


try:
    from app.services.ai_service import AIService
    from app.core.exceptions import BaseAppError

    AI_SERVICE_AVAILABLE = True
except ImportError as e:
    if "genai" in str(e):
        AI_SERVICE_AVAILABLE = False
        AIService = None
        BaseAppError = None
    else:
        raise


@pytest.mark.skipif(not AI_SERVICE_AVAILABLE, reason="Google GenAI SDK not available")
class TestAIServiceUnit:
    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_zero_wait_retry, mock_env_vars, mock_ai_client):
        mock_client_instance = MagicMock()
        mock_ai_client.return_value = mock_client_instance
        self.mock_client_instance = mock_client_instance
        mock_client_instance.reset_mock()

    @pytest.mark.asyncio
    async def test_gemini_api_failure(self, mock_populated_transaction):
        self.mock_client_instance.models.generate_content.side_effect = ConnectionError("API Key Invalid")

        with pytest.raises(BaseAppError) as exc_info:
            ai_service = AIService()
            await ai_service.analyze_transactions([mock_populated_transaction])

        assert "AI analysis failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_ai_response(self, mock_populated_transaction):
        mock_response = MagicMock()
        mock_response.text = ""

        ai_service = AIService()
        with patch.object(ai_service.client.models, "generate_content", return_value=mock_response):
            result = await ai_service.analyze_transactions([mock_populated_transaction])

        assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_only_ai_response(self, mock_populated_transaction):
        mock_response = MagicMock()
        mock_response.text = "   \n\t  "
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_populated_transaction])

        assert result == "   \n\t  ".strip()

    @pytest.mark.asyncio
    async def test_retry_mechanism_exhaustion(self, mock_populated_transaction):
        ai_service = AIService()
        with patch.object(ai_service.client.models, "generate_content", side_effect=TimeoutError("Rate limit exceeded")):
            with pytest.raises(BaseAppError) as exc_info:
                await ai_service.analyze_transactions([mock_populated_transaction])

            assert "AI analysis failed" in str(exc_info.value)
            assert ai_service.client.models.generate_content.call_count == 3

    @pytest.mark.asyncio
    async def test_daily_report_with_empty_transactions(self):
        ai_service = AIService()
        result = await ai_service.generate_daily_report([])

        assert "No transactions found" in result
        assert "Daily Transaction Report" in result

    @pytest.mark.asyncio
    async def test_daily_report_ai_failure(self, mock_populated_transaction):
        ai_service = AIService()
        with patch.object(ai_service.client.models, "generate_content", side_effect=OSError("Service unavailable")):
            with pytest.raises(BaseAppError) as exc_info:
                await ai_service.generate_daily_report([mock_populated_transaction])

            assert "AI analysis failed" in str(exc_info.value)

    def test_ai_service_missing_api_key(self, mock_env_vars):
        import os
        from unittest.mock import patch

        env_without_api_key = mock_env_vars.copy()
        del env_without_api_key["GEMINI_API_KEY"]

        with patch.dict(os.environ, env_without_api_key, clear=True):
            with pytest.raises(ValueError) as exc_info:
                AIService()

            assert "GEMINI_API_KEY environment variable is not set" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transaction_formatting_with_missing_timestamp(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)
        mock_transaction.timestamp = None

        ai_service = AIService()
        formatted = ai_service._format_transactions_for_ai([mock_transaction])

        assert len(formatted) == 1
        assert formatted[0]["timestamp"] is None

    @pytest.mark.asyncio
    async def test_transaction_formatting_with_missing_description(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)
        mock_transaction.description = ""

        ai_service = AIService()
        formatted = ai_service._format_transactions_for_ai([mock_transaction])

        assert len(formatted) == 1
        assert formatted[0]["description"] == ""

    @pytest.mark.asyncio
    async def test_successful_ai_analysis_happy_path(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        mock_response = MagicMock()
        mock_response.text = "Analysis complete: Transaction is normal"
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        assert result == "Analysis complete: Transaction is normal"
        self.mock_client_instance.models.generate_content.assert_called_once()

        call_args = self.mock_client_instance.models.generate_content.call_args
        prompt = call_args[1]["contents"] if "contents" in call_args[1] else call_args[0][1]
        assert mock_transaction_data["tx_id"] in prompt
        assert str(mock_transaction_data["amount"]) in prompt

    @pytest.mark.asyncio
    async def test_successful_daily_report_generation(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        mock_response = MagicMock()
        mock_response.text = "Financial analysis shows healthy transaction patterns"
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.generate_daily_report([mock_transaction])

        assert "DAILY TRANSACTION ANALYSIS REPORT" in result
        assert "=" * 50 in result
        assert "Financial analysis shows healthy transaction patterns" in result
        self.mock_client_instance.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_sdk_returns_none(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        self.mock_client_instance.models.generate_content.return_value = None

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        assert result == ""

    @pytest.mark.asyncio
    async def test_sdk_returns_object_without_text(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        mock_response = MagicMock()
        del mock_response.text
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        assert result == ""

    @pytest.mark.asyncio
    async def test_ai_response_has_text_none(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        mock_response = MagicMock()
        mock_response.text = None
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        assert result == ""

    @pytest.mark.asyncio
    async def test_prompt_contains_required_transaction_fields(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        mock_response = MagicMock()
        mock_response.text = "Analysis complete"
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        await ai_service.analyze_transactions([mock_transaction])

        call_args = self.mock_client_instance.models.generate_content.call_args
        prompt = call_args[1]["contents"] if "contents" in call_args[1] else call_args[0][1]

        assert mock_transaction_data["tx_id"] in prompt
        assert str(mock_transaction_data["amount"]) in prompt
        assert mock_transaction_data["sender_account"] in prompt
        assert mock_transaction_data["receiver_account"] in prompt
        assert mock_transaction_data["description"] in prompt

    @pytest.mark.asyncio
    async def test_retry_stops_after_successful_attempt(self, mock_transaction_data):
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        mock_response = MagicMock()
        mock_response.text = "Success on retry"

        ai_service = AIService()
        with patch.object(
            ai_service.client.models,
            "generate_content",
            side_effect=[TimeoutError("First attempt failed"), mock_response],
        ) as mock_generate:
            with patch("app.services.ai_service.wait_exponential", return_value=tenacity.wait_fixed(0)):
                result = await ai_service.analyze_transactions([mock_transaction])

        assert result == "Success on retry"
        assert mock_generate.call_count == 2
