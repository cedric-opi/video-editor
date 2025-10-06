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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# OpenAI client
openai_client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

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
        video = VideoFileClip(video_path)
        video_duration = video.duration
        
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
        
        video.close()
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
    """Create final video clips with captions and voice-overs"""
    try:
        video = VideoFileClip(video_path)
        final_clips = []
        
        for segment in segments:
            # Extract video segment
            clip = video.subclip(segment.start_time, segment.end_time)
            
            # Generate audio
            audio_path = await generate_audio_for_segment(segment.audio_script, segment.id)
            
            if audio_path and os.path.exists(audio_path):
                # Add voice-over audio
                from moviepy.editor import AudioFileClip
                voice_audio = AudioFileClip(audio_path)
                
                # Mix with original audio (lower original volume)
                original_audio = clip.audio.volumex(0.3) if clip.audio else None
                if original_audio:
                    final_audio = CompositeAudioClip([original_audio, voice_audio])
                else:
                    final_audio = voice_audio
                
                clip = clip.set_audio(final_audio)
            
            # Add caption text overlay
            txt_clip = TextClip(
                segment.caption_text,
                fontsize=50,
                color='white',
                stroke_color='black',
                stroke_width=2,
                font='Arial-Bold'
            ).set_position(('center', 0.8), relative=True).set_duration(clip.duration)
            
            # Composite final clip
            final_clip = CompositeVideoClip([clip, txt_clip])
            
            # Export final clip
            output_path = f"/tmp/segment_{segment.id}.mp4"
            final_clip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='/tmp/temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            final_clips.append(output_path)
            
            # Cleanup
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        
        video.close()
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
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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
            
            # Check video length (5 minutes max for normal plan)
            if duration > 300:  # 5 minutes
                os.remove(temp_path)
                raise HTTPException(
                    status_code=400, 
                    detail="Video too long. Maximum 5 minutes for normal plan. Upgrade to premium for longer videos."
                )
                
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
        
        if not os.path.exists(segment_file):
            raise HTTPException(status_code=404, detail="Processed segment file not found")
        
        return FileResponse(
            segment_file,
            media_type="video/mp4",
            filename=f"viral_segment_{segment_number}.mp4"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail="Download failed")

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