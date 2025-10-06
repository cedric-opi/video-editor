"""
Main FastAPI application server - Refactored and organized
"""
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Request
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import shutil
import ffmpeg
import uuid
from typing import Dict, Any
from pathlib import Path

# Import organized modules
from config import CORS_ORIGINS, MAX_FILE_SIZE, PREMIUM_PLANS
from database import connect_to_mongo, close_mongo_connection, get_database
from models import VideoUpload, CheckoutRequest, ProcessingStatus, ViralAnalysis, VideoSegment
from services.user_service import UserService  
from services.payment_service import MomoPayService
from services.video_service import VideoService
from payment_gateways import PaymentGatewayManager, PaymentRequest, PaymentProvider

# Create the main app
app = FastAPI(
    title="Viral Video Analyzer - Million Dollar System",
    description="AI-powered viral video analysis and segmentation system with global payments",
    version="2.0.0"
)

# Create API router
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize services
user_service = UserService()
video_service = VideoService()
momo_service = MomoPayService()

# Application startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")  
async def shutdown_db_client():
    await close_mongo_connection()

# ===== VIDEO PROCESSING ENDPOINTS =====

@api_router.get("/")
async def root():
    return {
        "message": "Viral Video Analyzer API - Million Dollar System",
        "version": "2.0.0",
        "status": "operational"
    }

@api_router.post("/video/analyze")
async def analyze_video_direct(background_tasks: BackgroundTasks, file: UploadFile = File(...), user_email: str = None):
    """Direct video analysis endpoint with GPT-5 enhanced processing"""
    try:
        # Validate file
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        # Check file size
        if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum 500MB allowed")
        
        # Create video record
        video_id = str(uuid.uuid4())
        
        # Save uploaded file
        temp_path = f"/tmp/analyze_{video_id}.mp4"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get video duration and validate
        try:
            probe = ffmpeg.probe(temp_path)
            duration = float(probe['streams'][0]['duration'])
            file_size = os.path.getsize(temp_path)
            
            # Check premium status and duration limits
            if user_email:
                premium_status = await user_service.check_user_premium_status(user_email)
                max_duration = premium_status["max_video_duration"]
                
                if duration > max_duration:
                    os.remove(temp_path)
                    if premium_status["is_premium"]:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Video too long. Maximum {max_duration//60} minutes for your premium plan."
                        )
                    else:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Video too long. Maximum 5 minutes for free plan. Upgrade to premium for longer videos (up to 30 minutes)."
                        )
            else:
                # No user email, use free plan limits
                if duration > 300:  # 5 minutes
                    os.remove(temp_path)
                    raise HTTPException(
                        status_code=400, 
                        detail="Video too long. Maximum 5 minutes for free plan. Upgrade to premium for longer videos (up to 30 minutes)."
                    )
                
        except HTTPException:
            raise
        except Exception as e:
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail="Invalid video file")
        
        # Perform immediate GPT-5 enhanced analysis
        logger.info(f"🧠 Starting direct GPT-5 video analysis for {video_id}")
        
        # Get usage tier
        usage_tier = await user_service.check_user_usage_limits(user_email)
        
        # Analyze video content with GPT-5
        analysis_data = await video_service.analyze_video_content(temp_path, duration, user_email)
        
        # Create intelligent segments
        segments = await video_service.create_video_segments(temp_path, analysis_data, video_id)
        
        # Create video upload record for tracking
        video_upload = VideoUpload(
            id=video_id,
            filename=temp_path,
            original_filename=file.filename,
            file_size=file_size,
            duration=duration,
            user_email=user_email
        )
        
        db = await get_database()
        await db.video_uploads.insert_one(video_upload.dict())
        
        # Save analysis
        analysis = ViralAnalysis(
            video_id=video_id,
            analysis_text=analysis_data.get("analysis_text", ""),
            viral_techniques=analysis_data.get("viral_techniques", []),
            engagement_factors=analysis_data.get("engagement_factors", []),
            content_summary=analysis_data.get("content_summary", ""),
            viral_score=analysis_data.get("viral_score", 0.0),
            content_type=analysis_data.get("content_type", ""),
            editing_recommendations=analysis_data.get("editing_recommendations", [])
        )
        await db.viral_analysis.insert_one(analysis.dict())
        
        # Save segments
        for segment in segments:
            segment_dict = segment.dict()
            segment_dict["quality_tier"] = usage_tier
            await db.video_segments.insert_one(segment_dict)
        
        # Prepare response with enhanced GPT-5 fields
        response_data = {
            "video_id": video_id,
            "analysis": {
                "viral_score": analysis_data.get("viral_score", 0.0),
                "content_type": analysis_data.get("content_type", ""),
                "target_audience": analysis_data.get("target_audience", ""),
                "viral_techniques": analysis_data.get("viral_techniques", []),
                "engagement_factors": analysis_data.get("engagement_factors", []),
                "content_summary": analysis_data.get("content_summary", ""),
                "analysis_text": analysis_data.get("analysis_text", ""),
                "hook_strategy": analysis_data.get("hook_strategy", ""),
                "platform_optimization": analysis_data.get("platform_optimization", {}),
                "editing_recommendations": analysis_data.get("editing_recommendations", []),
                "subtitle_strategy": analysis_data.get("subtitle_strategy", ""),
                "viral_prediction": analysis_data.get("viral_prediction", ""),
                "quality_tier": usage_tier,
                "analysis_model": analysis_data.get("analysis_model", "gpt-5")
            },
            "segments": [
                {
                    "segment_id": seg.segment_number,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "duration": seg.duration,
                    "purpose": getattr(seg, 'purpose', f"Segment {seg.segment_number}"),
                    "viral_score": getattr(seg, 'viral_score', seg.highlight_score),
                    "caption_text": seg.caption_text,
                    "subtitle_content": getattr(seg, 'subtitle_content', ''),
                    "editing_notes": getattr(seg, 'editing_notes', ''),
                    "engagement_elements": getattr(seg, 'engagement_elements', [])
                }
                for seg in segments
            ],
            "video_info": {
                "duration": duration,
                "file_size": file_size,
                "original_filename": file.filename
            },
            "processing_info": {
                "gpt5_enhanced": True,
                "max_segments_applied": len(segments) <= 3 if duration > 180 else True,
                "intelligent_segmentation": True,
                "professional_subtitles": True
            }
        }
        
        logger.info(f"✅ Direct GPT-5 analysis completed for {video_id} - Viral Score: {analysis_data.get('viral_score', 'N/A')}")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Direct analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@api_router.post("/upload-video")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), user_email: str = None):
    """Upload video for advanced AI processing"""
    try:
        # Validate file
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        # Check file size
        if hasattr(file, 'size') and file.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum 500MB allowed")
        
        # Create video record
        video_id = str(uuid.uuid4())
        
        # Save uploaded file
        temp_path = f"/tmp/upload_{video_id}.mp4"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get video duration and validate
        try:
            probe = ffmpeg.probe(temp_path)
            duration = float(probe['streams'][0]['duration'])
            file_size = os.path.getsize(temp_path)
            
            # Check premium status and duration limits
            if user_email:
                premium_status = await user_service.check_user_premium_status(user_email)
                max_duration = premium_status["max_video_duration"]
                
                if duration > max_duration:
                    os.remove(temp_path)
                    if premium_status["is_premium"]:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Video too long. Maximum {max_duration//60} minutes for your premium plan."
                        )
                    else:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Video too long. Maximum 5 minutes for free plan. Upgrade to premium for longer videos (up to 30 minutes)."
                        )
            else:
                # No user email, use free plan limits
                if duration > 300:  # 5 minutes
                    os.remove(temp_path)
                    raise HTTPException(
                        status_code=400, 
                        detail="Video too long. Maximum 5 minutes for free plan. Upgrade to premium for longer videos (up to 30 minutes)."
                    )
                
        except HTTPException:
            raise
        except Exception as e:
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail="Invalid video file")
        
        # Create video upload record
        video_upload = VideoUpload(
            id=video_id,
            filename=temp_path,
            original_filename=file.filename,
            file_size=file_size,
            duration=duration,
            user_email=user_email
        )
        
        db = await get_database()
        await db.video_uploads.insert_one(video_upload.dict())
        
        # Start enhanced background processing
        background_tasks.add_task(process_video_pipeline, video_id, temp_path, duration, user_email)
        
        # Initialize processing status
        await db.processing_status.insert_one(ProcessingStatus(
            video_id=video_id,
            status="processing",
            progress=10,
            message="🚀 Video uploaded! Starting AI-powered viral analysis..."
        ).dict())
        
        return {
            "video_id": video_id,
            "message": "Video uploaded successfully",
            "duration": duration,
            "status": "processing",
            "estimated_completion": "2-3 minutes"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

async def process_video_pipeline(video_id: str, video_path: str, duration: float, user_email: str = None):
    """Enhanced video processing pipeline with professional AI editing"""
    try:
        db = await get_database()
        
        # Get usage tier and update count
        usage_tier = await user_service.check_user_usage_limits(user_email)
        if user_email:
            await user_service.update_user_usage_count(user_email, video_id)
        
        # Step 1: Advanced AI Analysis
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "analyzing", "progress": 25, "message": f"🤖 AI analyzing video content ({usage_tier} quality)..."}}
        )
        
        analysis_data = await video_service.analyze_video_content(video_path, duration, user_email)
        
        # Save analysis
        analysis = ViralAnalysis(
            video_id=video_id,
            analysis_text=analysis_data.get("analysis_text", ""),
            viral_techniques=analysis_data.get("viral_techniques", []),
            engagement_factors=analysis_data.get("engagement_factors", []),
            content_summary=analysis_data.get("content_summary", ""),
            viral_score=analysis_data.get("viral_score", 0.0),
            content_type=analysis_data.get("content_type", ""),
            editing_recommendations=analysis_data.get("editing_recommendations", [])
        )
        await db.viral_analysis.insert_one(analysis.dict())
        
        # Step 2: Create optimized segments  
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "segmenting", "progress": 45, "message": "✂️ Creating viral-optimized segments (max 3 for long videos)..."}}
        )
        
        segments = await video_service.create_video_segments(video_path, analysis_data, video_id)
        
        # Step 3: Generate professional captions
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "generating", "progress": 65, "message": "📝 Generating viral captions with embedded subtitles..."}}
        )
        
        segments = await generate_enhanced_captions(segments, usage_tier)
        
        # Save segments with quality tier
        for segment in segments:
            segment_dict = segment.dict()
            segment_dict["quality_tier"] = usage_tier
            await db.video_segments.insert_one(segment_dict)
        
        # Step 4: Create professional clips with embedded subtitles
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "finalizing", "progress": 85, "message": "🎬 Creating professional clips with embedded subtitles..."}}
        )
        
        final_clips = await video_service.create_professional_clips(video_path, segments, usage_tier)
        
        # Completion message based on tier
        if usage_tier == "premium":
            message = "🎉 Premium quality viral clips ready! Unlimited processing."
        elif usage_tier == "free_high":
            remaining = await user_service.get_user_usage_status(user_email)
            message = f"✨ High-quality clips ready! {remaining.get('remaining_high_quality', 0)} premium edits left."
        else:
            message = "✅ Standard clips ready. Upgrade for premium viral editing!"
        
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "completed", "progress": 100, "message": message}}
        )
        
        logger.info(f"🎬 Professional video processing completed: {video_id} ({usage_tier} tier)")
        
    except Exception as e:
        logger.error(f"Processing pipeline error: {str(e)}")
        db = await get_database()
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "error", "progress": 0, "message": f"Processing failed: {str(e)}"}}
        )

async def generate_enhanced_captions(segments: list, usage_tier: str):
    """Generate enhanced captions using VideoService"""
    try:
        for segment in segments:
            if usage_tier in ["premium", "free_high"]:
                # Premium caption generation
                if not segment.caption_text.startswith(('🔥', '✨', '💥', '⚡', '🚀')):
                    emojis = ['🔥', '✨', '💥', '⚡', '🚀', '👀', '😱', '🤯']
                    emoji = emojis[hash(segment.caption_text) % len(emojis)]
                    segment.caption_text = f"{emoji} {segment.caption_text}"
        
        return segments
    except Exception as e:
        logger.error(f"Caption generation error: {str(e)}")
        return segments

# ===== STATUS AND INFO ENDPOINTS =====

@api_router.get("/processing-status/{video_id}")
async def get_processing_status(video_id: str):
    """Get video processing status"""
    db = await get_database()
    status = await db.processing_status.find_one({"video_id": video_id})
    if not status:
        raise HTTPException(status_code=404, detail="Video not found")
    
    status.pop('_id', None)
    return status

@api_router.get("/video-analysis/{video_id}")
async def get_video_analysis(video_id: str):
    """Get AI analysis results"""
    db = await get_database()
    analysis = await db.viral_analysis.find_one({"video_id": video_id})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    analysis.pop('_id', None)
    return analysis

@api_router.get("/video-segments/{video_id}")
async def get_video_segments(video_id: str):
    """Get video segments with quality info"""
    db = await get_database()
    segments = await db.video_segments.find({"video_id": video_id}).to_list(length=None)
    
    for segment in segments:
        segment.pop('_id', None)
    
    return {"segments": segments}

@api_router.get("/video-list")
async def get_video_list():
    """Get list of processed videos"""
    db = await get_database()
    videos = await db.video_uploads.find().to_list(length=None)
    
    for video in videos:
        video.pop('_id', None)
        # Get processing status
        status = await db.processing_status.find_one({"video_id": video['id']})
        video['processing_status'] = status.get('status', 'unknown') if status else 'unknown'
    
    return {"videos": videos}

@api_router.get("/download-segment/{video_id}/{segment_number}")
async def download_segment(video_id: str, segment_number: int):
    """Download processed video segment"""
    try:
        db = await get_database()
        
        # Find segment
        segment = await db.video_segments.find_one({
            "video_id": video_id,
            "segment_number": segment_number
        })
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        segment_file = f"/tmp/segment_{segment['id']}.mp4"
        
        # Create on-demand if not exists
        if not os.path.exists(segment_file):
            video = await db.video_uploads.find_one({"id": video_id})
            if not video or not os.path.exists(video['filename']):
                raise HTTPException(status_code=404, detail="Source video not found")
            
            # Create segment on-demand
            try:
                (
                    ffmpeg
                    .input(video['filename'], ss=segment['start_time'], t=segment['duration'])
                    .output(segment_file, vcodec='libx264', acodec='aac', preset='fast')
                    .overwrite_output()
                    .run(quiet=True)
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail="Failed to create segment")
        
        if not os.path.exists(segment_file) or os.path.getsize(segment_file) == 0:
            raise HTTPException(status_code=404, detail="Segment file unavailable")
        
        return FileResponse(
            segment_file,
            media_type="video/mp4",
            filename=f"viral_segment_{segment_number}.mp4"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# ===== USER AND PAYMENT ENDPOINTS =====

@api_router.get("/premium-plans")
async def get_premium_plans():
    """Get available premium plans with multiple currencies"""
    return {"plans": PREMIUM_PLANS}

@api_router.get("/payment-providers")
async def get_payment_providers(region: str = None):
    """Get available payment providers for region including MomoPay"""
    
    # Regional payment provider preferences
    regional_preferences = {
        "VN": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
        "TH": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
        "LA": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL],
        "KH": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL],
        "MM": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL],
        "US": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
        "CA": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
        "GB": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
        "EU": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
        "default": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL, PaymentProvider.MOMOPAY]
    }
    
    provider_info = {
        PaymentProvider.STRIPE: {
            "name": "Credit Card (Stripe)",
            "description": "Pay with Visa, Mastercard, American Express",
            "supported_regions": ["US", "CA", "GB", "EU", "AU"],
            "currencies": ["USD", "EUR", "GBP", "CAD", "AUD"]
        },
        PaymentProvider.PAYPAL: {
            "name": "PayPal",
            "description": "Pay with PayPal account or credit card",
            "supported_regions": ["Global"],
            "currencies": ["USD", "EUR", "GBP", "CAD", "AUD", "JPY"]
        },
        PaymentProvider.MOMOPAY: {
            "name": "MomoPay",
            "description": "ATM Cards, Credit Cards, MoMo Wallet (Vietnam)",
            "supported_regions": ["VN", "TH", "LA", "KH", "MM"],
            "currencies": ["VND", "USD"]
        }
    }
    
    available_providers = regional_preferences.get(region, regional_preferences["default"])
    
    return {
        "available_providers": [
            {"provider": provider.value, **provider_info.get(provider, {})}
            for provider in available_providers
        ],
        "recommended": available_providers[0].value if available_providers else "stripe"
    }

@api_router.post("/premium-status")
async def check_premium_status(request: Dict[str, str]):
    """Check user premium status"""
    user_email = request.get("user_email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email is required")
    
    status = await user_service.check_user_premium_status(user_email)
    return status

@api_router.post("/usage-status")
async def get_usage_status(request: Dict[str, str]):
    """Get user usage status including quality limits"""
    user_email = request.get("user_email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email is required")
    
    status = await user_service.get_user_usage_status(user_email)
    return status

@api_router.post("/create-checkout")
async def create_checkout_session(request: CheckoutRequest):
    """Create payment checkout with MomoPay support"""
    try:
        if request.plan_type not in PREMIUM_PLANS:
            raise HTTPException(status_code=400, detail="Invalid plan type")
        
        plan = PREMIUM_PLANS[request.plan_type]
        
        # Handle MomoPay specifically
        if request.payment_provider == "momopay":
            # Determine currency and amount
            if request.currency and request.currency.upper() == "VND":
                amount = plan["price_vnd"]
                currency = "VND"
            else:
                amount = plan["price_usd"] 
                currency = "USD"
            
            # Create success/cancel URLs
            success_url = f"{request.origin_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}&provider=momopay"
            cancel_url = f"{request.origin_url}/payment-cancel"
            
            # Create MomoPay payment
            result = await momo_service.create_payment(
                user_email=request.user_email,
                plan_type=request.plan_type,
                amount=amount,
                currency=currency,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            if result["success"]:
                return {
                    "provider": "momopay",
                    "checkout_url": result["checkout_url"],
                    "session_id": result["session_id"],
                    "order_id": result["order_id"],
                    "amount_vnd": result.get("amount_vnd"),
                    "amount_usd": result.get("amount_usd"),
                    "qr_code_url": result.get("qr_code_url"),
                    "deep_link": result.get("deep_link")
                }
            else:
                raise HTTPException(status_code=500, detail=result["error"])
        
        else:
            # Handle other payment providers (Stripe, PayPal)
            payment_manager = PaymentGatewayManager(request.origin_url)
            
            provider = PaymentProvider(request.payment_provider) if request.payment_provider else None
            
            payment_request = PaymentRequest(
                amount=plan["price_usd"],
                currency="USD",
                user_email=request.user_email,
                plan_type=request.plan_type,
                success_url=f"{request.origin_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}&provider={{PROVIDER}}",
                cancel_url=f"{request.origin_url}/payment-cancel"
            )
            
            response = await payment_manager.create_payment(payment_request, provider, request.user_region)
            
            if response.status.value == "failed":
                raise HTTPException(status_code=500, detail=response.error)
            
            return {
                "provider": response.provider.value,
                "checkout_url": response.checkout_url,
                "session_id": response.session_id,
                "order_id": response.order_id
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Checkout failed: {str(e)}")

@api_router.post("/webhook/momopay")
async def momo_webhook(request: Request):
    """Handle MomoPay webhooks"""
    try:
        body = await request.body()
        payload = await request.json()
        
        result = await momo_service.handle_webhook(payload)
        
        if result["success"]:
            logger.info(f"MomoPay webhook processed: {result}")
            return {"status": "success"}
        else:
            logger.error(f"MomoPay webhook failed: {result}")
            raise HTTPException(status_code=400, detail="Webhook processing failed")
            
    except Exception as e:
        logger.error(f"MomoPay webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/video/{video_id}")
async def delete_video(video_id: str):
    """Delete video and associated data"""
    try:
        db = await get_database()
        
        # Delete from database
        await db.video_uploads.delete_one({"id": video_id})
        await db.viral_analysis.delete_one({"video_id": video_id})
        await db.video_segments.delete_many({"video_id": video_id})
        await db.processing_status.delete_one({"video_id": video_id})
        
        # Delete files
        video_file = f"/tmp/upload_{video_id}.mp4"
        if os.path.exists(video_file):
            os.remove(video_file)
        
        # Delete segment files
        segments = await db.video_segments.find({"video_id": video_id}).to_list(length=None)
        for segment in segments:
            segment_file = f"/tmp/segment_{segment['id']}.mp4"
            if os.path.exists(segment_file):
                os.remove(segment_file)
        
        return {"message": "Video deleted successfully"}
        
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail="Delete failed")

# Include router and configure middleware
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)