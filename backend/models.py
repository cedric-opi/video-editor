"""
Data models for the Viral Video Analyzer system
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

class VideoUpload(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_filename: str
    file_size: int
    duration: float
    status: str = "uploaded"
    user_email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ViralAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    video_id: str
    analysis_text: str
    viral_techniques: List[str]
    engagement_factors: List[str]
    content_summary: str
    viral_score: float = 0.0
    content_type: Optional[str] = None
    target_audience: Optional[str] = None
    editing_recommendations: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VideoSegment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    video_id: str
    segment_number: int
    start_time: float
    end_time: float
    duration: float
    caption_text: str
    audio_script: str
    highlight_score: float
    purpose: Optional[str] = None
    viral_score: Optional[float] = None
    subtitle_content: Optional[str] = None
    quality_tier: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProcessingStatus(BaseModel):
    video_id: str
    status: str
    progress: int
    message: str
    error: Optional[str] = None

class PremiumPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_email: str
    plan_type: str  # "premium_monthly", "premium_yearly"
    amount: float
    currency: str = "usd"
    status: str = "pending"
    stripe_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_email: str
    amount: float
    currency: str = "usd"
    plan_type: str
    payment_provider: str
    session_id: str
    payment_status: str = "pending"
    status: str = "initiated"
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CheckoutRequest(BaseModel):
    plan_type: str
    user_email: str
    origin_url: str
    payment_provider: Optional[str] = None
    user_region: Optional[str] = None
    currency: Optional[str] = "USD"

class UsageStatus(BaseModel):
    user_email: str
    usage_tier: str
    videos_processed: int
    remaining_high_quality: int
    is_premium: bool
    plan_type: Optional[str] = None