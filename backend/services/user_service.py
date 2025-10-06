"""
User management and premium status services
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import logging
from database import get_database
from config import PREMIUM_PLANS, FREE_HIGH_QUALITY_VIDEOS

logger = logging.getLogger(__name__)

class UserService:
    
    @staticmethod
    async def check_user_premium_status(user_email: str) -> Dict[str, Any]:
        """Check if user has active premium subscription"""
        try:
            db = await get_database()
            
            # Find active premium plan
            active_plan = await db.premium_plans.find_one({
                "user_email": user_email,
                "status": "active",
                "expires_at": {"$gt": datetime.now(timezone.utc)}
            })
            
            if active_plan:
                plan_config = PREMIUM_PLANS[active_plan["plan_type"]]
                return {
                    "is_premium": True,
                    "plan_type": active_plan["plan_type"],
                    "expires_at": active_plan["expires_at"],
                    "max_video_duration": plan_config["max_video_duration"]
                }
            else:
                return {
                    "is_premium": False,
                    "max_video_duration": 300  # 5 minutes for free users
                }
        except Exception as e:
            logger.error(f"Error checking premium status: {str(e)}")
            return {
                "is_premium": False,
                "max_video_duration": 300
            }
    
    @staticmethod
    async def check_user_usage_limits(user_email: str) -> str:
        """Check user's usage tier based on processing history"""
        if not user_email:
            return "standard"
        
        try:
            # Check premium status first
            premium_status = await UserService.check_user_premium_status(user_email)
            if premium_status["is_premium"]:
                return "premium"
            
            # Count user's video processing in last 30 days
            db = await get_database()
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            user_videos = await db.video_uploads.count_documents({
                "user_email": user_email,
                "created_at": {"$gte": thirty_days_ago}
            })
            
            # Usage tiers for free users
            if user_videos < FREE_HIGH_QUALITY_VIDEOS:
                return "free_high"  # High quality for first videos
            else:
                return "standard"   # Reduced quality after limit
                
        except Exception as e:
            logger.error(f"Error checking usage limits: {str(e)}")
            return "standard"
    
    @staticmethod
    async def get_user_usage_status(user_email: str) -> Dict[str, Any]:
        """Get detailed user usage status for frontend display"""
        if not user_email:
            return {
                "usage_tier": "standard",
                "videos_processed": 0,
                "remaining_high_quality": 0,
                "is_premium": False
            }
        
        try:
            premium_status = await UserService.check_user_premium_status(user_email)
            if premium_status["is_premium"]:
                return {
                    "usage_tier": "premium",
                    "videos_processed": "unlimited",
                    "remaining_high_quality": "unlimited",
                    "is_premium": True,
                    "plan_type": premium_status["plan_type"]
                }
            
            # Count videos processed in last 30 days
            db = await get_database()
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            videos_count = await db.video_uploads.count_documents({
                "user_email": user_email,
                "created_at": {"$gte": thirty_days_ago}
            })
            
            remaining_high_quality = max(0, FREE_HIGH_QUALITY_VIDEOS - videos_count)
            
            return {
                "usage_tier": "free_high" if remaining_high_quality > 0 else "standard",
                "videos_processed": videos_count,
                "remaining_high_quality": remaining_high_quality,
                "is_premium": False
            }
            
        except Exception as e:
            logger.error(f"Error getting usage status: {str(e)}")
            return {
                "usage_tier": "standard",
                "videos_processed": 0,
                "remaining_high_quality": 0,
                "is_premium": False
            }
    
    @staticmethod
    async def update_user_usage_count(user_email: str, video_id: str):
        """Update user's usage count for tracking"""
        if not user_email:
            return
        
        try:
            db = await get_database()
            await db.video_uploads.update_one(
                {"id": video_id},
                {"$set": {"user_email": user_email}}
            )
        except Exception as e:
            logger.error(f"Error updating usage count: {str(e)}")
    
    @staticmethod
    async def activate_premium_plan(user_email: str, plan_type: str):
        """Activate premium plan for user"""
        try:
            plan = PREMIUM_PLANS[plan_type]
            
            # Calculate expiration date
            expires_at = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
            
            db = await get_database()
            
            # Deactivate any existing premium plans
            await db.premium_plans.update_many(
                {"user_email": user_email, "status": "active"},
                {"$set": {"status": "inactive"}}
            )
            
            # Create new premium plan
            from models import PremiumPlan
            premium_plan = PremiumPlan(
                user_email=user_email,
                plan_type=plan_type,
                amount=plan["price_usd"],
                currency="usd",
                status="active",
                expires_at=expires_at
            )
            
            await db.premium_plans.insert_one(premium_plan.dict())
            
            logger.info(f"Activated premium plan {plan_type} for user {user_email}")
            
        except Exception as e:
            logger.error(f"Error activating premium plan: {str(e)}")