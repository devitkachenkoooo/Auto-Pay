import pytest
from unittest.mock import MagicMock, patch
import tenacity

pytest.skip("Legacy module: moved to tests/unit/", allow_module_level=True)

# Try to import AI service, but skip tests if Google GenAI SDK is not available
try:
    from app.services.ai_service import AIService
    from app.core.exceptions import BaseAppError
    from app.models import Transaction

    AI_SERVICE_AVAILABLE = True
except ImportError as e:
    if "genai" in str(e):
        AI_SERVICE_AVAILABLE = False
        AIService = None
        BaseAppError = None
        Transaction = None
    else:
        raise


@pytest.mark.skipif(not AI_SERVICE_AVAILABLE, reason="Google GenAI SDK not available")
class TestAIServiceUnit:
    """Unit tests for AI service failure scenarios"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mock_zero_wait_retry, mock_env_vars, mock_ai_client):
        """Automatically apply zero wait retry, mock environment, and AI client for all tests"""
        # Mock the genai client to prevent actual API calls
        mock_client_instance = MagicMock()
        mock_ai_client.return_value = mock_client_instance
        self.mock_client_instance = mock_client_instance

        # Reset the mock before each test to ensure clean state
        mock_client_instance.reset_mock()

    @pytest.mark.asyncio
    async def test_gemini_api_failure(self, mock_populated_transaction):
        """Test handling of Gemini API failures"""
        # Mock API failure using the autouse fixture
        self.mock_client_instance.models.generate_content.side_effect = ConnectionError(
            "API Key Invalid"
        )

        # Use the standardized retry patching fixture
        with pytest.raises(BaseAppError) as exc_info:
            ai_service = AIService()
            await ai_service.analyze_transactions([mock_populated_transaction])

        # Should get the wrapped error message
        assert "AI analysis failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_ai_response(self, mock_populated_transaction):
        """Test handling of empty AI responses"""
        # Mock empty response
        mock_response = MagicMock()
        mock_response.text = ""

        ai_service = AIService()
        with patch.object(
            ai_service.client.models, "generate_content", return_value=mock_response
        ):
            result = await ai_service.analyze_transactions([mock_populated_transaction])

        # Should return empty string without error
        assert result == ""

    @pytest.mark.asyncio
    async def test_whitespace_only_ai_response(self, mock_populated_transaction):
        """Test handling of whitespace-only AI responses"""
        # Mock whitespace-only response using the autouse fixture
        mock_response = MagicMock()
        mock_response.text = "   \n\t  "
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_populated_transaction])

        # Should return stripped whitespace due to defensive programming
        assert result == "   \n\t  ".strip()

    @pytest.mark.asyncio
    async def test_retry_mechanism_exhaustion(self, mock_populated_transaction):
        """Test retry mechanism after 3 failed attempts"""
        # Mock timeout error on the underlying client method to preserve retry decorator
        ai_service = AIService()
        with patch.object(
            ai_service.client.models,
            "generate_content",
            side_effect=TimeoutError("Rate limit exceeded"),
        ):
            # Use the standardized retry patching fixture
            with pytest.raises(BaseAppError) as exc_info:
                await ai_service.analyze_transactions([mock_populated_transaction])

            # Should get the wrapped error message
            assert "AI analysis failed" in str(exc_info.value)
            # Verify the method was called exactly 3 times (1 initial + 2 retries)
            assert ai_service.client.models.generate_content.call_count == 3

    @pytest.mark.asyncio
    async def test_daily_report_with_empty_transactions(self, mock_ai_client):
        """Test daily report generation with no transactions"""
        ai_service = AIService()
        result = await ai_service.generate_daily_report([])

        assert "No transactions found" in result
        assert "Daily Transaction Report" in result

    @pytest.mark.asyncio
    async def test_daily_report_ai_failure(self, mock_populated_transaction):
        """Test daily report generation when AI analysis fails"""
        # Mock service unavailable error (OSError is in the retry list)
        ai_service = AIService()
        with patch.object(
            ai_service.client.models,
            "generate_content",
            side_effect=OSError("Service unavailable"),
        ):
            # Use the standardized retry patching fixture
            with pytest.raises(BaseAppError) as exc_info:
                await ai_service.generate_daily_report([mock_populated_transaction])

            # The error message comes from the analyze_transactions method, not generate_daily_report
            assert "AI analysis failed" in str(exc_info.value)

    def test_ai_service_missing_api_key(self, mock_env_vars):
        """Test AI service initialization when API key is missing"""
        # Temporarily remove the API key from the mocked environment
        import os
        from unittest.mock import patch

        # Create a copy of the test env without the API key
        env_without_api_key = mock_env_vars.copy()
        del env_without_api_key["GEMINI_API_KEY"]

        with patch.dict(os.environ, env_without_api_key, clear=True):
            with pytest.raises(ValueError) as exc_info:
                AIService()

            assert "GEMINI_API_KEY environment variable is not set" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_transaction_formatting_with_missing_timestamp(
        self, mock_transaction_data
    ):
        """Test transaction formatting when timestamp is None"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)
        mock_transaction.timestamp = None  # Ensure timestamp is None

        ai_service = AIService()
        formatted = ai_service._format_transactions_for_ai([mock_transaction])

        assert len(formatted) == 1
        assert formatted[0]["timestamp"] is None

    @pytest.mark.asyncio
    async def test_transaction_formatting_with_missing_description(
        self, mock_transaction_data
    ):
        """Test transaction formatting when description is empty"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)
        mock_transaction.description = ""  # Empty description

        ai_service = AIService()
        formatted = ai_service._format_transactions_for_ai([mock_transaction])

        assert len(formatted) == 1
        assert formatted[0]["description"] == ""

    @pytest.mark.asyncio
    async def test_successful_ai_analysis_happy_path(self, mock_transaction_data):
        """Test successful AI analysis (Happy Path)"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        # Mock successful AI response using the autouse fixture
        mock_response = MagicMock()
        mock_response.text = "Analysis complete: Transaction is normal"
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        # Verify expected text is returned
        assert result == "Analysis complete: Transaction is normal"

        # Verify AI was called exactly once
        self.mock_client_instance.models.generate_content.assert_called_once()

        # Verify prompt contains transaction data
        call_args = self.mock_client_instance.models.generate_content.call_args
        prompt = (
            call_args[1]["contents"] if "contents" in call_args[1] else call_args[0][1]
        )
        assert mock_transaction_data["tx_id"] in prompt
        assert str(mock_transaction_data["amount"]) in prompt

    @pytest.mark.asyncio
    async def test_successful_daily_report_generation(self, mock_transaction_data):
        """Test successful daily report generation"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        # Mock successful AI analysis using the autouse fixture
        mock_response = MagicMock()
        mock_response.text = "Financial analysis shows healthy transaction patterns"
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.generate_daily_report([mock_transaction])

        # Verify fully formed report is returned
        assert "DAILY TRANSACTION ANALYSIS REPORT" in result
        assert "=" * 50 in result
        assert "Financial analysis shows healthy transaction patterns" in result

        # Verify AI was called exactly once
        self.mock_client_instance.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_sdk_returns_none(self, mock_transaction_data):
        """Test behavior when AI SDK returns None"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        # Mock SDK returning None using the autouse fixture
        self.mock_client_instance.models.generate_content.return_value = None

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        # Should return empty string due to defensive programming
        assert result == ""

    @pytest.mark.asyncio
    async def test_sdk_returns_object_without_text(self, mock_transaction_data):
        """Test behavior when AI response object has no text attribute"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        # Mock response without text attribute using the autouse fixture
        mock_response = MagicMock()
        del mock_response.text  # Remove text attribute
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        # Should return empty string due to defensive programming
        assert result == ""

    @pytest.mark.asyncio
    async def test_ai_response_has_text_none(self, mock_transaction_data):
        """Test behavior when AI response has text = None"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        # Mock response with text = None using the autouse fixture
        mock_response = MagicMock()
        mock_response.text = None
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        result = await ai_service.analyze_transactions([mock_transaction])

        # Should return empty string due to defensive programming
        assert result == ""

    @pytest.mark.asyncio
    async def test_prompt_contains_required_transaction_fields(
        self, mock_transaction_data
    ):
        """Test that prompt contains all required transaction fields"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        # Mock response using the autouse fixture
        mock_response = MagicMock()
        mock_response.text = "Analysis complete"
        self.mock_client_instance.models.generate_content.return_value = mock_response

        ai_service = AIService()
        await ai_service.analyze_transactions([mock_transaction])

        # Get the prompt from the call
        call_args = self.mock_client_instance.models.generate_content.call_args
        prompt = (
            call_args[1]["contents"] if "contents" in call_args[1] else call_args[0][1]
        )

        # Verify all required fields are present
        assert mock_transaction_data["tx_id"] in prompt
        assert str(mock_transaction_data["amount"]) in prompt
        assert mock_transaction_data["sender_account"] in prompt
        assert mock_transaction_data["receiver_account"] in prompt
        assert mock_transaction_data["description"] in prompt

    @pytest.mark.asyncio
    async def test_retry_stops_after_successful_attempt(self, mock_transaction_data):
        """Test that retry stops after successful attempt"""
        mock_transaction = MagicMock()
        mock_transaction.__dict__.update(mock_transaction_data)

        # Mock first call fails, second succeeds
        mock_response = MagicMock()
        mock_response.text = "Success on retry"

        ai_service = AIService()
        with patch.object(
            ai_service.client.models,
            "generate_content",
            side_effect=[TimeoutError("First attempt failed"), mock_response],
        ):
            # Patch retry wait to 0 for faster tests
            with patch(
                "app.services.ai_service.wait_exponential",
                return_value=tenacity.wait_fixed(0),
            ):
                result = await ai_service.analyze_transactions([mock_transaction])

            # Verify successful result
            assert result == "Success on retry"

            # Verify exactly 2 calls were made (1 failed + 1 successful)
            assert ai_service.client.models.generate_content.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
