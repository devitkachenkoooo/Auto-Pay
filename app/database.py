import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models import Transaction
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def init_db():
    """
    Initialize MongoDB connection and Beanie ODM

    Raises:
        Exception: If database connection fails
    """
    try:
        # Create MongoDB client
        mongo_url = os.getenv("MONGO_URL")
        if not mongo_url:
            raise ValueError("MONGO_URL environment variable is not set")

        client = AsyncIOMotorClient(mongo_url)

        # Test the connection
        await client.admin.command("ping")

        # Initialize Beanie with the database and document models
        # Beanie will automatically create the database and collection
        await init_beanie(
            database=client.get_default_database(), document_models=[Transaction]
        )
        logger.info("✅ MongoDB connected and Beanie initialized!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {str(e)}")
        raise Exception(f"Database initialization failed: {str(e)}")
