"""
Database configuration and utilities
"""
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DB_NAME
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    database = None

db_instance = Database()

async def get_database():
    """Get database instance"""
    return db_instance.database

async def connect_to_mongo():
    """Create database connection"""
    try:
        db_instance.client = AsyncIOMotorClient(MONGO_URL)
        db_instance.database = db_instance.client[DB_NAME]
        
        # Test the connection
        await db_instance.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
        # Create indexes for better performance
        await create_indexes()
        
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Close database connection"""
    if db_instance.client:
        db_instance.client.close()
        logger.info("Disconnected from MongoDB")

async def create_indexes():
    """Create database indexes for performance"""
    try:
        db = db_instance.database
        
        # Video uploads indexes
        await db.video_uploads.create_index("id")
        await db.video_uploads.create_index("user_email")
        await db.video_uploads.create_index("created_at")
        
        # Video segments indexes  
        await db.video_segments.create_index("video_id")
        await db.video_segments.create_index("segment_number")
        
        # Payment transactions indexes
        await db.payment_transactions.create_index("session_id")
        await db.payment_transactions.create_index("user_email")
        await db.payment_transactions.create_index("payment_status")
        
        # Premium plans indexes
        await db.premium_plans.create_index("user_email")
        await db.premium_plans.create_index("status")
        await db.premium_plans.create_index("expires_at")
        
        # Processing status indexes
        await db.processing_status.create_index("video_id")
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")

# Export database instance for use in other modules
async def get_db():
    """Helper function to get database instance"""
    return await get_database()