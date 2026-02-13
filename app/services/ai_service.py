"""
AI service for analyzing transactions using Google Gemini.

Fixes applied:
    - Replaced deprecated asyncio.get_event_loop() with asyncio.get_running_loop()
    - Narrowed retry scope (only retries on transient errors, not all exceptions)
    - Error wrapping no longer exposes raw SDK exception messages to callers
    - Removed emoji from log messages
"""

import os
import logging
import asyncio
from typing import List, Dict, Any
from google import genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.models import Transaction
from app.core.exceptions import BaseAppError

logger = logging.getLogger(__name__)


class AIService:
    """AI service for analyzing transactions using Google Gemini"""

    def __init__(self):
        """Initialize the AI service with the Google GenAI client"""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")

        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "models/gemini-2.0-flash"
        logger.info(f"AI Service initialized with {self.model_id}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    def _call_ai_model(self, prompt: str):
        """Synchronous AI model call for use with retry mechanism."""
        return self.client.models.generate_content(model=self.model_id, contents=prompt)

    async def analyze_transactions(self, transactions: List[Transaction]) -> str:
        """Analyze transactions using Gemini AI with retry mechanism."""
        try:
            transaction_data = self._format_transactions_for_ai(transactions)
            prompt = self._create_analysis_prompt(transaction_data)

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self._call_ai_model,
                prompt,
            )

            # Defensive programming: Check response validity
            if response is None:
                logger.error("AI SDK returned None response")
                return ""

            if not hasattr(response, "text"):
                logger.error("AI response missing 'text' attribute")
                return ""

            result = response.text.strip() if response.text else ""

            logger.info(f"Successfully analyzed {len(transactions)} transactions")
            return result

        except BaseAppError:
            raise
        except Exception as e:
            logger.error("Failed to analyze transactions", exc_info=True)
            raise BaseAppError(
                "AI analysis failed",
                details="ai_service_analyze_transactions",
            ) from e

    def _format_transactions_for_ai(
        self, transactions: List[Transaction]
    ) -> List[Dict[str, Any]]:
        """Convert transaction objects to a format suitable for AI analysis."""
        formatted_data = []
        for tx in transactions:
            formatted_data.append(
                {
                    "id": tx.tx_id,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "sender": tx.sender_account,
                    "receiver": tx.receiver_account,
                    "status": tx.status,
                    "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                    "description": tx.description,
                }
            )
        return formatted_data

    def _create_analysis_prompt(self, transaction_data: List[Dict[str, Any]]) -> str:
        """Create a comprehensive prompt for transaction analysis."""
        total_amount = sum(tx["amount"] for tx in transaction_data)
        transaction_count = len(transaction_data)
        successful_tx = len(
            [
                tx
                for tx in transaction_data
                if tx["status"] in ("success", "completed")
            ]
        )
        pending_tx = len([tx for tx in transaction_data if tx["status"] == "pending"])

        prompt = f"""
        You are a financial analyst AI. Analyze the following transaction data and provide a comprehensive report.

        TRANSACTION SUMMARY:
        - Total Transactions: {transaction_count}
        - Total Amount: ${total_amount:.2f}
        - Successful Transactions: {successful_tx}
        - Pending Transactions: {pending_tx}

        DETAILED TRANSACTIONS:
        {self._format_transactions_for_prompt(transaction_data)}

        Please provide a detailed analysis including:
        1. Overall transaction patterns and trends
        2. Notable observations (large amounts, frequent senders/receivers)
        3. Success rate analysis
        4. Any potential concerns or anomalies
        5. Recommendations for optimization

        Format the response in a clear, human-readable report with sections and bullet points.
        """
        return prompt

    def _format_transactions_for_prompt(
        self, transaction_data: List[Dict[str, Any]]
    ) -> str:
        """Format transaction data for inclusion in the AI prompt."""
        formatted_lines = []
        for i, tx in enumerate(transaction_data, 1):
            line = f"{i}. ID: {tx['id']}, Amount: ${tx['amount']:.2f}, "
            line += f"Currency: {tx['currency']}, Sender: {tx['sender']}, "
            line += f"Receiver: {tx['receiver']}, Status: {tx['status']}"
            if tx["timestamp"]:
                line += f", Time: {tx['timestamp']}"
            if tx["description"]:
                line += f", Description: {tx['description']}"
            formatted_lines.append(line)
        return "\n".join(formatted_lines)

    async def generate_daily_report(self, transactions: List[Transaction]) -> str:
        """Generate a daily transaction report using AI."""
        try:
            if not transactions:
                return (
                    "Daily Transaction Report\n\nNo transactions found for this period."
                )

            analysis = await self.analyze_transactions(transactions)

            report = "DAILY TRANSACTION ANALYSIS REPORT\n"
            report += "=" * 50 + "\n\n"
            report += analysis
            return report

        except BaseAppError:
            raise
        except Exception as e:
            logger.error("Failed to generate daily report", exc_info=True)
            raise BaseAppError(
                "Daily report generation failed",
                details="ai_service_generate_daily_report",
            ) from e


# Global AI service instance
ai_service = None


def get_ai_service() -> AIService:
    """Get or create the AI service instance."""
    global ai_service
    if ai_service is None:
        ai_service = AIService()
    return ai_service
