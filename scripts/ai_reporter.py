#!/usr/bin/env python3
"""
AI Transaction Reporter Script

This script fetches daily transactions from MongoDB, calculates basic metrics,
and generates a human-readable report using Gemini AI.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import List
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import init_db
from app.models import Transaction
from app.services.ai_service import get_ai_service

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def fetch_daily_transactions() -> List[Transaction]:
    """
    Fetch transactions from the last 24 hours

    Returns:
        List of Transaction objects from the past day
    """
    try:
        # Calculate the time range (last 24 hours)
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Fetch transactions from the last 24 hours
        transactions = await Transaction.find(
            Transaction.timestamp >= yesterday
        ).to_list()

        logger.info(f"📊 Found {len(transactions)} transactions in the last 24 hours")
        return transactions

    except Exception as e:
        logger.error(f"❌ Failed to fetch daily transactions: {str(e)}")
        raise


def calculate_basic_metrics(transactions: List[Transaction]) -> dict:
    """
    Calculate basic transaction metrics

    Args:
        transactions: List of Transaction objects

    Returns:
        Dictionary containing basic metrics
    """
    if not transactions:
        return {
            "total_count": 0,
            "total_amount": 0.0,
            "average_amount": 0.0,
            "successful_count": 0,
            "pending_count": 0,
            "success_rate": 0.0,
        }

    total_amount = sum(tx.amount for tx in transactions)
    successful_count = len([tx for tx in transactions if tx.status == "completed"])
    pending_count = len([tx for tx in transactions if tx.status == "pending"])

    metrics = {
        "total_count": len(transactions),
        "total_amount": total_amount,
        "average_amount": total_amount / len(transactions),
        "successful_count": successful_count,
        "pending_count": pending_count,
        "success_rate": (successful_count / len(transactions)) * 100,
    }

    return metrics


def print_metrics_summary(metrics: dict) -> None:
    """Print a summary of basic metrics to console"""
    print("\n" + "=" * 50)
    print("📈 BASIC TRANSACTION METRICS")
    print("=" * 50)
    print(f"Total Transactions: {metrics['total_count']}")
    print(f"Total Amount: ${metrics['total_amount']:.2f}")
    print(f"Average Amount: ${metrics['average_amount']:.2f}")
    print(f"Successful Transactions: {metrics['successful_count']}")
    print(f"Pending Transactions: {metrics['pending_count']}")
    print(f"Success Rate: {metrics['success_rate']:.1f}%")
    print("=" * 50)


async def generate_ai_report(transactions: List[Transaction]) -> str:
    """
    Generate AI-powered analysis report

    Args:
        transactions: List of Transaction objects

    Returns:
        AI-generated report as string
    """
    try:
        ai_service = get_ai_service()
        report = await ai_service.generate_daily_report(transactions)
        return report

    except Exception as e:
        logger.error(f"❌ Failed to generate AI report: {str(e)}")
        raise


async def save_report_to_file(report: str, filename: str = None) -> str:
    """
    Save the generated report to a file

    Args:
        report: The report content to save
        filename: Optional custom filename

    Returns:
        Path to the saved file
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transaction_report_{timestamp}.txt"

    # Create reports directory if it doesn't exist
    reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    filepath = os.path.join(reports_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"📄 Report saved to: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"❌ Failed to save report: {str(e)}")
        raise


async def main():
    """Main function to run the AI reporter"""
    try:
        print("🚀 Starting AI Transaction Reporter...")

        # Initialize database connection
        print("🔌 Connecting to database...")
        await init_db()

        # Fetch daily transactions
        print("📊 Fetching daily transactions...")
        transactions = await fetch_daily_transactions()

        if not transactions:
            print("⚠️  No transactions found in the last 24 hours.")
            return

        # Calculate and display basic metrics
        metrics = calculate_basic_metrics(transactions)
        print_metrics_summary(metrics)

        # Generate AI report
        print("🤖 Generating AI analysis report...")
        ai_report = await generate_ai_report(transactions)

        # Display the report
        print("\n" + ai_report)

        # Save report to file
        report_path = await save_report_to_file(ai_report)
        print("\n✅ Report generation completed successfully!")
        print(f"📁 Report saved to: {report_path}")

    except Exception as e:
        logger.error(f"❌ Reporter failed: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
