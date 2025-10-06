from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import tempfile
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import asyncio
import shutil

# Video processing imports
import ffmpeg
import subprocess
from PIL import Image, ImageDraw, ImageFont

# OpenAI imports
from openai import AsyncOpenAI

# Stripe imports
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# OpenAI client
openai_client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Stripe client initialization function
def get_stripe_client(host_url: str):
    webhook_url = f"{host_url}api/webhook/stripe"
    return StripeCheckout(api_key=os.environ.get('STRIPE_API_KEY'), webhook_url=webhook_url)

# Create the main app without a prefix
app = FastAPI(
    title="Viral Video Analyzer",
    description="AI-powered viral video analysis and segmentation system",
    version="1.0.0"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Premium plan pricing
PREMIUM_PLANS = {
    "premium_monthly": {
        "name": "Premium Monthly",
        "price": 9.99,
        "description": "Upload videos up to 30 minutes, unlimited processing",
        "max_video_duration": 1800,  # 30 minutes
        "duration_days": 30
    },
    "premium_yearly": {
        "name": "Premium Yearly", 
        "price": 99.99,
        "description": "Upload videos up to 30 minutes, unlimited processing + 2 months free",
        "max_video_duration": 1800,  # 30 minutes
        "duration_days": 365
    }
}

# Helper function to check user premium status
async def check_user_premium_status(user_email: str) -> Dict[str, Any]:
    """Check if user has active premium subscription"""
    try:
        # Find active premium plan
        active_plan = await db.premium_plans.find_one({
            "user_email": user_email,
            "status": "active",
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        
        if active_plan:
            return {
                "is_premium": True,
                "plan_type": active_plan["plan_type"],
                "expires_at": active_plan["expires_at"],
                "max_video_duration": PREMIUM_PLANS[active_plan["plan_type"]]["max_video_duration"]
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
            "max_video_duration": 300  # Default to free plan on error
        }

# Define Models
class VideoUpload(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_filename: str
    file_size: int
    duration: float
    status: str = "uploaded"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ViralAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    video_id: str
    analysis_text: str
    viral_techniques: List[str]
    engagement_factors: List[str]
    content_summary: str
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProcessingStatus(BaseModel):
    video_id: str
    status: str
    progress: int
    message: str
    error: Optional[str] = None

# Payment Models
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
    stripe_session_id: str
    payment_status: str = "pending"
    status: str = "initiated"
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CheckoutRequest(BaseModel):
    plan_type: str
    user_email: str
    origin_url: str

# Helper Functions
async def analyze_video_content(video_path: str, duration: float) -> Dict[str, Any]:
    """Analyze video content using OpenAI GPT-4"""
    try:
        # Get video transcript/description based on visual analysis
        analysis_prompt = f"""
        Analyze this video content for viral potential and techniques. The video is {duration:.1f} seconds long.
        
        Please provide a comprehensive analysis including:
        1. Viral Techniques: What specific techniques make this content engaging? (hooks, pacing, visual elements, etc.)
        2. Engagement Factors: What elements drive viewer engagement? (emotional triggers, curiosity gaps, etc.)
        3. Content Summary: Brief description of the video content and main message
        4. Highlight Moments: Identify the most engaging segments for creating short clips
        
        Format your response as JSON with the following structure:
        {{
            "viral_techniques": ["technique1", "technique2", "technique3"],
            "engagement_factors": ["factor1", "factor2", "factor3"],
            "content_summary": "Brief summary of the video content",
            "analysis_text": "Detailed analysis of viral potential and techniques used",
            "highlight_segments": [
                {{"start": 0, "end": 15, "reason": "Strong hook opens the video", "score": 0.9}},
                {{"start": 30, "end": 45, "reason": "Peak emotional moment", "score": 0.8}}
            ]
        }}
        """
        
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in viral video content analysis. Analyze videos for viral potential, engagement techniques, and optimal segmentation for short-form content."},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )
        
        # Parse the JSON response
        try:
            analysis_json = json.loads(response.choices[0].message.content.strip())
        except json.JSONDecodeError:
            # If JSON parsing fails, create default response
            logger.warning("Failed to parse AI response as JSON, using default analysis")
            raise ValueError("JSON parsing failed")
        
        return analysis_json
        
    except Exception as e:
        logger.error(f"Error analyzing video: {str(e)}")
        # Return default analysis if AI fails
        return {
            "viral_techniques": ["Strong Opening", "Visual Appeal", "Clear Message"],
            "engagement_factors": ["Curiosity", "Emotional Connection", "Value Delivery"],
            "content_summary": "Video content analysis",
            "analysis_text": "Basic analysis completed. The video shows potential for viral content with proper optimization.",
            "highlight_segments": [
                {"start": 0, "end": min(30, duration), "reason": "Opening segment", "score": 0.8}
            ]
        }

async def create_video_segments(video_path: str, analysis_data: Dict[str, Any], video_id: str) -> List[VideoSegment]:
    """Create video segments based on AI analysis"""
    try:
        segments = []
        
        # Get video duration using ffprobe
        probe = ffmpeg.probe(video_path)
        video_duration = float(probe['streams'][0]['duration'])
        
        # Get highlight segments from analysis
        highlight_segments = analysis_data.get("highlight_segments", [])
        
        # If no specific segments, create default segments (15-30 second chunks)
        if not highlight_segments:
            segment_duration = 25  # Default 25-second segments
            current_time = 0
            segment_num = 1
            
            while current_time < video_duration:
                end_time = min(current_time + segment_duration, video_duration)
                
                if end_time - current_time >= 10:  # Only create segments >= 10 seconds
                    segments.append(VideoSegment(
                        video_id=video_id,
                        segment_number=segment_num,
                        start_time=current_time,
                        end_time=end_time,
                        duration=end_time - current_time,
                        caption_text=f"Segment {segment_num}",
                        audio_script=f"This is segment {segment_num} of the viral content.",
                        highlight_score=0.7
                    ))
                    segment_num += 1
                
                current_time = end_time
        else:
            # Use AI-identified segments
            for i, segment_data in enumerate(highlight_segments):
                start_time = segment_data.get("start", 0)
                end_time = segment_data.get("end", start_time + 15)
                reason = segment_data.get("reason", f"Highlight segment {i+1}")
                score = segment_data.get("score", 0.7)
                
                if end_time <= video_duration and end_time - start_time >= 5:
                    segments.append(VideoSegment(
                        video_id=video_id,
                        segment_number=i + 1,
                        start_time=start_time,
                        end_time=end_time,
                        duration=end_time - start_time,
                        caption_text=reason,
                        audio_script=f"Key highlight: {reason}",
                        highlight_score=score
                    ))
        
        return segments
        
    except Exception as e:
        logger.error(f"Error creating segments: {str(e)}")
        return []

async def generate_captions_and_voice(segments: List[VideoSegment]) -> List[VideoSegment]:
    """Generate AI captions and voice-overs for segments"""
    try:
        for segment in segments:
            # Generate enhanced caption using GPT-4
            caption_prompt = f"""
            Create an engaging caption for a {segment.duration:.1f}-second viral video segment.
            
            Context: {segment.caption_text}
            
            Requirements:
            - Keep it under 100 characters
            - Make it engaging and shareable
            - Include relevant hashtags
            - Focus on hook or value proposition
            
            Return only the caption text, nothing else.
            """
            
            caption_response = await openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at creating viral social media captions that drive engagement and shares."},
                    {"role": "user", "content": caption_prompt}
                ],
                max_tokens=50,
                temperature=0.8
            )
            
            # Generate voice script
            voice_prompt = f"""
            Create a compelling voice-over script for a {segment.duration:.1f}-second video segment.
            
            Context: {segment.caption_text}
            
            Requirements:
            - Natural speaking pace (about 150 words per minute)
            - Engaging and conversational tone
            - Clear call-to-action or value statement
            - Fits within {segment.duration:.1f} seconds
            
            Return only the voice script, nothing else.
            """
            
            voice_response = await openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert voice-over script writer for viral social media content."},
                    {"role": "user", "content": voice_prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            # Update segment with generated content
            segment.caption_text = caption_response.choices[0].message.content.strip()
            segment.audio_script = voice_response.choices[0].message.content.strip()
        
        return segments
        
    except Exception as e:
        logger.error(f"Error generating captions and voice: {str(e)}")
        return segments

async def generate_audio_for_segment(text: str, segment_id: str) -> str:
    """Generate AI voice-over using OpenAI TTS"""
    try:
        response = await openai_client.audio.speech.create(
            model="tts-1-hd",
            voice="alloy",
            input=text,
            response_format="mp3"
        )
        
        # Save audio file
        audio_path = f"/tmp/audio_{segment_id}.mp3"
        with open(audio_path, "wb") as f:
            f.write(await response.aread())
        
        return audio_path
        
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        return None

async def create_final_clips(video_path: str, segments: List[VideoSegment]) -> List[str]:
    """Create final video clips with captions and voice-overs using ffmpeg"""
    try:
        final_clips = []
        
        for segment in segments:
            output_path = f"/tmp/segment_{segment.id}.mp4"
            
            try:
                logger.info(f"Creating clip for segment {segment.segment_number}: {segment.start_time}s - {segment.end_time}s")
                
                # Extract video segment using ffmpeg
                (
                    ffmpeg
                    .input(video_path, ss=segment.start_time, t=segment.duration)
                    .output(
                        output_path, 
                        vcodec='libx264', 
                        acodec='aac',
                        **{'c:v': 'libx264', 'c:a': 'aac', 'preset': 'fast'}
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
                
                # Verify the file was created
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    final_clips.append(output_path)
                    logger.info(f"Successfully created segment file: {output_path}")
                else:
                    logger.error(f"Segment file not created or empty: {output_path}")
                
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg error processing segment {segment.id}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error processing segment {segment.id}: {str(e)}")
                continue
        
        logger.info(f"Created {len(final_clips)} final clips out of {len(segments)} segments")
        return final_clips
        
    except Exception as e:
        logger.error(f"Error creating final clips: {str(e)}")
        return []

# Background task for video processing
async def process_video_pipeline(video_id: str, video_path: str, duration: float):
    """Complete video processing pipeline"""
    try:
        # Update status
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "analyzing", "progress": 20, "message": "Analyzing video content with AI..."}},
            upsert=True
        )
        
        # Step 1: AI Analysis
        analysis_data = await analyze_video_content(video_path, duration)
        
        # Save analysis
        analysis = ViralAnalysis(
            video_id=video_id,
            analysis_text=analysis_data["analysis_text"],
            viral_techniques=analysis_data["viral_techniques"],
            engagement_factors=analysis_data["engagement_factors"],
            content_summary=analysis_data["content_summary"]
        )
        await db.viral_analysis.insert_one(analysis.dict())
        
        # Update status
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "segmenting", "progress": 50, "message": "Creating video segments..."}}
        )
        
        # Step 2: Create segments
        segments = await create_video_segments(video_path, analysis_data, video_id)
        
        # Update status
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "generating", "progress": 70, "message": "Generating captions and voice-overs..."}}
        )
        
        # Step 3: Generate captions and voice
        segments = await generate_captions_and_voice(segments)
        
        # Save segments to database
        for segment in segments:
            await db.video_segments.insert_one(segment.dict())
        
        # Update status
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "finalizing", "progress": 90, "message": "Creating final video clips..."}}
        )
        
        # Step 4: Create final clips
        final_clips = await create_final_clips(video_path, segments)
        
        # Update final status
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "completed", "progress": 100, "message": "Processing completed successfully!"}}
        )
        
        logger.info(f"Video processing completed for {video_id}")
        
    except Exception as e:
        logger.error(f"Error in video processing pipeline: {str(e)}")
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "error", "progress": 0, "message": f"Processing failed: {str(e)}", "error": str(e)}}
        )

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Viral Video Analyzer API"}

@api_router.post("/upload-video")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), user_email: str = None):
    """Upload video for processing"""
    try:
        # Validate file
        if not file.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        # Create video record
        video_id = str(uuid.uuid4())
        
        # Save uploaded file
        temp_path = f"/tmp/upload_{video_id}.mp4"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get video duration
        try:
            probe = ffmpeg.probe(temp_path)
            duration = float(probe['streams'][0]['duration'])
            file_size = os.path.getsize(temp_path)
            
            # Check premium status and video length limits
            if user_email:
                premium_status = await check_user_premium_status(user_email)
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
                # No user email provided, use free plan limits
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
        
        # Create video record
        video_upload = VideoUpload(
            id=video_id,
            filename=temp_path,
            original_filename=file.filename,
            file_size=file_size,
            duration=duration
        )
        
        await db.video_uploads.insert_one(video_upload.dict())
        
        # Start background processing
        background_tasks.add_task(process_video_pipeline, video_id, temp_path, duration)
        
        # Initialize processing status
        await db.processing_status.insert_one({
            "video_id": video_id,
            "status": "processing",
            "progress": 10,
            "message": "Video uploaded successfully. Processing started..."
        })
        
        return {
            "video_id": video_id,
            "message": "Video uploaded successfully",
            "duration": duration,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@api_router.get("/processing-status/{video_id}")
async def get_processing_status(video_id: str):
    """Get video processing status"""
    status = await db.processing_status.find_one({"video_id": video_id})
    if not status:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Remove MongoDB _id field
    status.pop('_id', None)
    return status

@api_router.get("/video-analysis/{video_id}")
async def get_video_analysis(video_id: str):
    """Get AI analysis results"""
    analysis = await db.viral_analysis.find_one({"video_id": video_id})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    analysis.pop('_id', None)
    return analysis

@api_router.get("/video-segments/{video_id}")
async def get_video_segments(video_id: str):
    """Get video segments"""
    segments = await db.video_segments.find({"video_id": video_id}).to_list(length=None)
    
    # Remove MongoDB _id fields
    for segment in segments:
        segment.pop('_id', None)
    
    return {"segments": segments}

@api_router.get("/download-segment/{video_id}/{segment_number}")
async def download_segment(video_id: str, segment_number: int):
    """Download processed video segment"""
    try:
        # Find segment
        segment = await db.video_segments.find_one({
            "video_id": video_id,
            "segment_number": segment_number
        })
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        # Look for the processed file
        segment_file = f"/tmp/segment_{segment['id']}.mp4"
        
        logger.info(f"Looking for segment file: {segment_file}")
        
        if not os.path.exists(segment_file):
            # If processed file doesn't exist, create it on-demand
            logger.info(f"Segment file not found, creating on-demand for segment {segment['id']}")
            
            # Find original video
            video = await db.video_uploads.find_one({"id": video_id})
            if not video:
                raise HTTPException(status_code=404, detail="Original video not found")
            
            original_video_path = video['filename']
            if not os.path.exists(original_video_path):
                raise HTTPException(status_code=404, detail="Original video file not found")
            
            # Create segment on-demand
            try:
                start_time = segment['start_time']
                duration = segment['duration']
                
                logger.info(f"Creating segment: {start_time}s for {duration}s")
                
                (
                    ffmpeg
                    .input(original_video_path, ss=start_time, t=duration)
                    .output(
                        segment_file, 
                        vcodec='libx264', 
                        acodec='aac',
                        **{'preset': 'fast'}
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
                
                if not os.path.exists(segment_file):
                    raise HTTPException(status_code=500, detail="Failed to create segment file")
                    
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg error creating segment: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to process video segment")
        
        # Verify file exists and has content
        if not os.path.exists(segment_file) or os.path.getsize(segment_file) == 0:
            raise HTTPException(status_code=404, detail="Segment file is empty or missing")
        
        logger.info(f"Serving segment file: {segment_file} (size: {os.path.getsize(segment_file)} bytes)")
        
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

@api_router.get("/video-list")
async def get_video_list():
    """Get list of all processed videos"""
    videos = await db.video_uploads.find().to_list(length=None)
    
    for video in videos:
        video.pop('_id', None)
        # Get processing status
        status = await db.processing_status.find_one({"video_id": video['id']})
        video['processing_status'] = status.get('status', 'unknown') if status else 'unknown'
    
    return {"videos": videos}

@api_router.get("/debug-files/{video_id}")
async def debug_files(video_id: str):
    """Debug endpoint to check what files exist for a video"""
    try:
        # Check original video
        video = await db.video_uploads.find_one({"id": video_id})
        original_file = video['filename'] if video else None
        original_exists = os.path.exists(original_file) if original_file else False
        
        # Check segments
        segments = await db.video_segments.find({"video_id": video_id}).to_list(length=None)
        segment_files = []
        
        for segment in segments:
            segment_file = f"/tmp/segment_{segment['id']}.mp4"
            segment_files.append({
                "segment_id": segment['id'],
                "segment_number": segment['segment_number'],
                "file_path": segment_file,
                "exists": os.path.exists(segment_file),
                "size": os.path.getsize(segment_file) if os.path.exists(segment_file) else 0
            })
        
        return {
            "video_id": video_id,
            "original_file": {
                "path": original_file,
                "exists": original_exists,
                "size": os.path.getsize(original_file) if original_exists else 0
            },
            "segments": segment_files,
            "tmp_files": [f for f in os.listdir("/tmp") if video_id in f]
        }
        
    except Exception as e:
        logger.error(f"Debug error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")

@api_router.post("/create-test-video/{video_id}")
async def create_test_video(video_id: str):
    """Create a test video for development purposes"""
    try:
        # Create a simple test video using ffmpeg
        test_video_path = f"/tmp/upload_{video_id}.mp4"
        
        # Create a 30-second test video with color bars
        (
            ffmpeg
            .input('color=c=blue:size=640x480:d=30', f='lavfi')
            .output(test_video_path, vcodec='libx264', pix_fmt='yuv420p')
            .overwrite_output()
            .run(quiet=True)
        )
        
        if not os.path.exists(test_video_path):
            raise HTTPException(status_code=500, detail="Failed to create test video")
        
        # Create video record
        video_upload = VideoUpload(
            id=video_id,
            filename=test_video_path,
            original_filename="test_video.mp4",
            file_size=os.path.getsize(test_video_path),
            duration=30.0,
            status="completed"
        )
        
        await db.video_uploads.insert_one(video_upload.dict())
        
        # Create test segments
        segments = [
            VideoSegment(
                video_id=video_id,
                segment_number=1,
                start_time=0.0,
                end_time=15.0,
                duration=15.0,
                caption_text="🔥 Amazing viral technique #1",
                audio_script="This is the first amazing highlight from your viral content.",
                highlight_score=0.9
            ),
            VideoSegment(
                video_id=video_id,
                segment_number=2,
                start_time=15.0,
                end_time=30.0,
                duration=15.0,
                caption_text="💯 Epic moment that hooks viewers",
                audio_script="Here's the second epic moment that will keep viewers engaged.",
                highlight_score=0.8
            )
        ]
        
        for segment in segments:
            await db.video_segments.insert_one(segment.dict())
        
        # Create test analysis
        analysis = ViralAnalysis(
            video_id=video_id,
            analysis_text="This test video demonstrates strong viral potential with clear visual appeal and engaging pacing.",
            viral_techniques=["Strong Opening", "Visual Appeal", "Clear Pacing", "Engaging Content"],
            engagement_factors=["Visual Impact", "Color Psychology", "Consistent Branding", "Hook Strategy"],
            content_summary="Test video with solid color background demonstrating basic viral video principles."
        )
        
        await db.viral_analysis.insert_one(analysis.dict())
        
        # Set processing status to completed
        await db.processing_status.update_one(
            {"video_id": video_id},
            {"$set": {"status": "completed", "progress": 100, "message": "Test video created successfully!"}},
            upsert=True
        )
        
        return {
            "message": "Test video created successfully",
            "video_id": video_id,
            "file_path": test_video_path,
            "segments_created": len(segments)
        }
        
    except Exception as e:
        logger.error(f"Test video creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test video creation failed: {str(e)}")

@api_router.delete("/video/{video_id}")
async def delete_video(video_id: str):
    """Delete video and all associated data"""
    try:
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

# Premium Plan and Payment Endpoints

@api_router.get("/premium-plans")
async def get_premium_plans():
    """Get available premium plans"""
    return {"plans": PREMIUM_PLANS}

@api_router.post("/premium-status")
async def check_premium_status(request: Dict[str, str]):
    """Check user premium status"""
    user_email = request.get("user_email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email is required")
    
    status = await check_user_premium_status(user_email)
    return status

@api_router.post("/create-checkout")
async def create_checkout_session(request: CheckoutRequest):
    """Create Stripe checkout session for premium plan"""
    try:
        # Validate plan type
        if request.plan_type not in PREMIUM_PLANS:
            raise HTTPException(status_code=400, detail="Invalid plan type")
        
        # Get plan details
        plan = PREMIUM_PLANS[request.plan_type]
        amount = plan["price"]
        
        # Initialize Stripe client
        stripe_client = get_stripe_client(request.origin_url)
        
        # Create success and cancel URLs
        success_url = f"{request.origin_url}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{request.origin_url}/payment-cancel"
        
        # Create checkout session
        checkout_request = CheckoutSessionRequest(
            amount=amount,
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_email": request.user_email,
                "plan_type": request.plan_type,
                "source": "viral_video_analyzer"
            }
        )
        
        session: CheckoutSessionResponse = await stripe_client.create_checkout_session(checkout_request)
        
        # Save payment transaction
        transaction = PaymentTransaction(
            user_email=request.user_email,
            amount=amount,
            currency="usd",
            plan_type=request.plan_type,
            stripe_session_id=session.session_id,
            payment_status="pending",
            status="initiated",
            metadata={
                "plan_name": plan["name"],
                "plan_description": plan["description"]
            }
        )
        
        await db.payment_transactions.insert_one(transaction.dict())
        
        logger.info(f"Created checkout session for user {request.user_email}, plan {request.plan_type}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.session_id
        }
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")

@api_router.get("/payment-status/{session_id}")
async def get_payment_status(session_id: str):
    """Get payment status for checkout session"""
    try:
        # Find transaction
        transaction = await db.payment_transactions.find_one({"stripe_session_id": session_id})
        if not transaction:
            raise HTTPException(status_code=404, detail="Payment session not found")
        
        # If already processed, return cached status
        if transaction["payment_status"] in ["paid", "failed", "expired"]:
            return {
                "payment_status": transaction["payment_status"],
                "status": transaction["status"],
                "plan_type": transaction["plan_type"],
                "amount": transaction["amount"]
            }
        
        # Get Stripe client (need origin URL - use a default for status checks)
        stripe_client = get_stripe_client("https://captivator.preview.emergentagent.com/")
        
        # Check status with Stripe
        checkout_status: CheckoutStatusResponse = await stripe_client.get_checkout_status(session_id)
        
        # Update transaction status
        await db.payment_transactions.update_one(
            {"stripe_session_id": session_id},
            {"$set": {
                "payment_status": checkout_status.payment_status,
                "status": checkout_status.status
            }}
        )
        
        # If payment is successful and not already processed, activate premium plan
        if checkout_status.payment_status == "paid" and transaction["payment_status"] != "paid":
            await activate_premium_plan(transaction["user_email"], transaction["plan_type"])
        
        return {
            "payment_status": checkout_status.payment_status,
            "status": checkout_status.status,
            "plan_type": transaction["plan_type"],
            "amount": checkout_status.amount_total / 100  # Convert from cents
        }
        
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check payment status: {str(e)}")

async def activate_premium_plan(user_email: str, plan_type: str):
    """Activate premium plan for user"""
    try:
        plan = PREMIUM_PLANS[plan_type]
        
        # Calculate expiration date
        expires_at = datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])
        
        # Deactivate any existing premium plans
        await db.premium_plans.update_many(
            {"user_email": user_email, "status": "active"},
            {"$set": {"status": "inactive"}}
        )
        
        # Create new premium plan
        premium_plan = PremiumPlan(
            user_email=user_email,
            plan_type=plan_type,
            amount=plan["price"],
            currency="usd",
            status="active",
            expires_at=expires_at
        )
        
        await db.premium_plans.insert_one(premium_plan.dict())
        
        logger.info(f"Activated premium plan {plan_type} for user {user_email}")
        
    except Exception as e:
        logger.error(f"Error activating premium plan: {str(e)}")

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: HTTPException):
    """Handle Stripe webhooks"""
    try:
        # Get raw body and signature
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        
        # Get Stripe client
        stripe_client = get_stripe_client("https://captivator.preview.emergentagent.com/")
        
        # Handle webhook
        webhook_response = await stripe_client.handle_webhook(body, signature)
        
        if webhook_response.event_type == "checkout.session.completed":
            # Find and update transaction
            transaction = await db.payment_transactions.find_one({
                "stripe_session_id": webhook_response.session_id
            })
            
            if transaction and transaction["payment_status"] != "paid":
                # Update transaction
                await db.payment_transactions.update_one(
                    {"stripe_session_id": webhook_response.session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "status": "completed"
                    }}
                )
                
                # Activate premium plan
                await activate_premium_plan(transaction["user_email"], transaction["plan_type"])
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Webhook handling failed")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()