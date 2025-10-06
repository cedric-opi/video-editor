"""
Advanced AI Video Processing Service with GPT-5 Integration
"""
import os
import json
import logging
import ffmpeg
import subprocess
import tempfile
import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone
from openai import AsyncOpenAI

from config import (
    OPENAI_API_KEY, MAX_SEGMENTS_LONG_VIDEO, SEGMENT_MIN_DURATION, 
    SEGMENT_MAX_DURATION, QUALITY_TIERS
)
from database import get_database
from models import VideoSegment, ViralAnalysis
from services.user_service import UserService
from services.enhanced_video_service import EnhancedVideoService

logger = logging.getLogger(__name__)

class VideoService:
    
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        # Initialize enhanced GPT-5 service
        try:
            self.enhanced_service = EnhancedVideoService()
            self.use_gpt5 = True
            logger.info("✅ GPT-5 Enhanced Video Service initialized successfully")
        except Exception as e:
            logger.warning(f"GPT-5 service initialization failed, falling back to GPT-4: {str(e)}")
            self.enhanced_service = None
            self.use_gpt5 = False
    
    async def analyze_video_content(self, video_path: str, duration: float, user_email: str = None) -> Dict[str, Any]:
        """Advanced AI video analysis for viral content creation using GPT-5"""
        try:
            # Use GPT-5 enhanced analysis if available
            if self.use_gpt5 and self.enhanced_service:
                logger.info("🧠 Using GPT-5 Enhanced Video Analysis")
                return await self.enhanced_service.analyze_video_with_gpt5(video_path, duration, user_email)
            
            # Fallback to GPT-4 analysis
            logger.info("⚡ Using GPT-4 Fallback Analysis")
            return await self._analyze_with_gpt4_fallback(video_path, duration, user_email)
            
        except Exception as e:
            logger.error(f"Error in video analysis: {str(e)}")
            usage_tier = await UserService.check_user_usage_limits(user_email)
            max_segments = MAX_SEGMENTS_LONG_VIDEO if duration > 180 else 5
            return self._create_default_analysis(duration, usage_tier, max_segments)
    
    async def _analyze_with_gpt4_fallback(self, video_path: str, duration: float, user_email: str = None) -> Dict[str, Any]:
        """Fallback GPT-4 analysis when GPT-5 is unavailable"""
        # Get user's quality tier
        usage_tier = await UserService.check_user_usage_limits(user_email)
        quality_config = QUALITY_TIERS.get(usage_tier, QUALITY_TIERS["standard"])
        
        # Determine segment strategy for long videos
        max_segments = MAX_SEGMENTS_LONG_VIDEO if duration > 180 else 5  # 3 segments max for videos > 3 minutes
        
        # Enhanced AI analysis prompt for viral video editing
        analysis_prompt = f"""
        You are a WORLD-CLASS VIRAL VIDEO EDITOR. Analyze this {duration:.1f}-second video to create the MOST ENGAGING content possible.

        VIDEO ANALYSIS REQUIREMENTS:
        1. **VIRAL POTENTIAL SCORING** (0.0-1.0 scale)
        2. **STRATEGIC SEGMENTATION** - Create exactly {max_segments} segments maximum
        3. **PROFESSIONAL SUBTITLES** - Generate embedded subtitle content for each segment
        4. **ENGAGEMENT OPTIMIZATION** - Hook viewers and maintain attention

        SEGMENTATION RULES:
        - For videos > 3 minutes: Create exactly 3 high-impact segments (20-60 seconds each)
        - For shorter videos: Create 3-5 segments (10-30 seconds each)
        - Each segment must be self-contained and viral-ready
        - Prioritize the most engaging moments with highest viral potential

        SUBTITLE REQUIREMENTS:
        - Generate accurate, engaging subtitles that appear IN the video
        - Use dynamic text that enhances the content (not just transcription)
        - Include emotional cues: [Exciting], [Surprising], [Important]
        - Make subtitles that work even with sound OFF
        - Time subtitles perfectly to match speech/action

        Quality Level: {usage_tier.upper()}
        Max Analysis Tokens: {quality_config["ai_analysis_tokens"]}

        Respond in this EXACT JSON format:
        {{
            "viral_score": 0.85,
            "content_type": "tutorial/entertainment/educational/promotional",
            "target_audience": "specific audience description",
            "viral_techniques": ["hook strategy", "emotional triggers", "visual elements"],
            "engagement_factors": ["curiosity gaps", "value delivery", "entertainment"],
            "content_summary": "compelling one-line description",
            "analysis_text": "detailed viral potential analysis",
            "optimized_segments": [
                {{
                    "segment_id": 1,
                    "start": 0,
                    "end": 25,
                    "duration": 25,
                    "purpose": "Hook - Grab attention instantly",
                    "viral_score": 0.9,
                    "caption_text": "🔥 This changes everything you know about...",
                    "description": "Opening hook with immediate value",
                    "subtitle_content": "00:00:00,000 --> 00:00:03,000\\nWatch this incredible transformation!\\n\\n00:00:03,000 --> 00:00:06,000\\n[Exciting] This will blow your mind...",
                    "editing_notes": "Add zoom effect, highlight key moments",
                    "engagement_elements": ["curiosity gap", "visual impact"]
                }}
            ],
            "editing_recommendations": ["Add dynamic text", "Use quick cuts"],
            "subtitle_strategy": "Use emotional cues and perfect timing"
        }}
        """
        
        # Use appropriate model and token limit based on quality tier
        model = "gpt-4" if usage_tier in ["premium", "free_high"] else "gpt-4"
        max_tokens = quality_config["ai_analysis_tokens"]
        
        response = await self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": "You are the world's best viral video editor with expertise in TikTok, Instagram Reels, and YouTube Shorts. You understand psychology, viral mechanics, and what makes content shareable. You create videos that consistently get millions of views."
                },
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        # Parse AI response
        try:
            analysis_json = json.loads(response.choices[0].message.content.strip())
            
            # Ensure compatibility with existing code
            if "optimized_segments" in analysis_json:
                analysis_json["highlight_segments"] = analysis_json["optimized_segments"]
            
            # Mark as GPT-4 analysis
            analysis_json["analysis_model"] = "gpt-4-fallback"
            return analysis_json
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse GPT-4 response, creating enhanced default analysis")
            return self._create_default_analysis(duration, usage_tier, max_segments)
    
    def _create_default_analysis(self, duration: float, usage_tier: str, max_segments: int) -> Dict[str, Any]:
        """Create enhanced default analysis when AI fails"""
        segments = []
        
        if usage_tier in ["premium", "free_high"]:
            # High quality default segments
            segment_count = min(max_segments, max(2, int(duration / 30)))
            segment_duration = duration / segment_count
            
            for i in range(segment_count):
                start_time = i * segment_duration
                end_time = min((i + 1) * segment_duration, duration)
                
                segments.append({
                    "segment_id": i + 1,
                    "start": start_time,
                    "end": end_time,
                    "duration": end_time - start_time,
                    "purpose": f"Viral Moment #{i + 1}",
                    "viral_score": 0.8 - (i * 0.1),
                    "caption_text": f"🚀 Amazing highlight #{i + 1}",
                    "description": "High-impact viral content segment",
                    "subtitle_content": self._generate_default_subtitles(start_time, end_time, i + 1),
                    "engagement_elements": ["visual appeal", "content value"]
                })
        else:
            # Standard quality - single segment
            segments = [{
                "segment_id": 1,
                "start": 0,
                "end": min(25, duration),
                "duration": min(25, duration),
                "purpose": "Main Highlight",
                "viral_score": 0.6,
                "caption_text": "✨ Check this out!",
                "description": "Main content highlight",
                "subtitle_content": "00:00:00,000 --> 00:00:05,000\nAmazing content ahead!\n\n"
            }]
        
        return {
            "viral_score": 0.7,
            "content_type": "general",
            "viral_techniques": ["Visual Appeal", "Engaging Content"],
            "engagement_factors": ["Interest", "Quality"],
            "content_summary": "Engaging video content with viral potential",
            "analysis_text": "Professional analysis reveals good viral potential with strategic editing.",
            "optimized_segments": segments,
            "highlight_segments": segments,
            "editing_recommendations": ["Add professional captions", "Optimize for mobile"],
            "quality_tier": usage_tier
        }
    
    def _generate_default_subtitles(self, start: float, end: float, segment_num: int) -> str:
        """Generate default subtitle content"""
        duration = end - start
        
        if duration <= 10:
            return f"00:00:00,000 --> 00:00:05,000\n🔥 Segment {segment_num} - Amazing!\n\n00:00:05,000 --> {self._format_srt_time(duration)}\n✨ Don't miss this part!\n\n"
        else:
            mid_time = duration / 2
            return f"00:00:00,000 --> {self._format_srt_time(mid_time)}\n🚀 Incredible moment #{segment_num}\n\n{self._format_srt_time(mid_time)} --> {self._format_srt_time(duration)}\n💥 This is game-changing!\n\n"
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds to SRT timestamp"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    async def create_video_segments(self, video_path: str, analysis_data: Dict[str, Any], video_id: str) -> List[VideoSegment]:
        """Create video segments with enhanced subtitle content"""
        try:
            segments = []
            
            # Get video duration
            probe = ffmpeg.probe(video_path)
            video_duration = float(probe['streams'][0]['duration'])
            
            # Use AI-optimized segments
            optimized_segments = analysis_data.get("optimized_segments", analysis_data.get("highlight_segments", []))
            
            if not optimized_segments:
                # Fallback to automatic segmentation with 3-segment limit for long videos
                max_segments = MAX_SEGMENTS_LONG_VIDEO if video_duration > 180 else 4
                segment_duration = min(video_duration / max_segments, SEGMENT_MAX_DURATION)
                
                current_time = 0
                segment_num = 1
                
                while current_time < video_duration and segment_num <= max_segments:
                    end_time = min(current_time + segment_duration, video_duration)
                    
                    if end_time - current_time >= SEGMENT_MIN_DURATION:
                        segments.append(VideoSegment(
                            video_id=video_id,
                            segment_number=segment_num,
                            start_time=current_time,
                            end_time=end_time,
                            duration=end_time - current_time,
                            caption_text=f"Segment {segment_num}",
                            audio_script=f"This is segment {segment_num} of viral content.",
                            highlight_score=0.7,
                            subtitle_content=self._generate_default_subtitles(current_time, end_time, segment_num)
                        ))
                        segment_num += 1
                    
                    current_time = end_time
            else:
                # Use AI-optimized segments
                for i, segment_data in enumerate(optimized_segments):
                    start_time = segment_data.get("start", 0)
                    end_time = segment_data.get("end", start_time + 15)
                    purpose = segment_data.get("purpose", f"Segment {i+1}")
                    score = segment_data.get("viral_score", 0.7)
                    subtitle_content = segment_data.get("subtitle_content", "")
                    
                    if end_time <= video_duration and end_time - start_time >= SEGMENT_MIN_DURATION:
                        segments.append(VideoSegment(
                            video_id=video_id,
                            segment_number=i + 1,
                            start_time=start_time,
                            end_time=end_time,
                            duration=end_time - start_time,
                            caption_text=segment_data.get("caption_text", purpose),
                            audio_script=segment_data.get("description", f"Key moment: {purpose}"),
                            highlight_score=score,
                            purpose=purpose,
                            viral_score=score,
                            subtitle_content=subtitle_content
                        ))
            
            return segments
            
        except Exception as e:
            logger.error(f"Error creating video segments: {str(e)}")
            return []
    
    async def create_professional_clips(self, video_path: str, segments: List[VideoSegment], usage_tier: str = "standard") -> List[str]:
        """Create professional video clips with embedded subtitles"""
        try:
            final_clips = []
            quality_config = QUALITY_TIERS.get(usage_tier, QUALITY_TIERS["standard"])
            
            for segment in segments:
                output_path = f"/tmp/segment_{segment.id}.mp4"
                
                try:
                    logger.info(f"Creating professional clip: Segment {segment.segment_number} ({segment.start_time}s - {segment.end_time}s)")
                    
                    # Create subtitle file
                    subtitle_file = await self._create_subtitle_file(segment, usage_tier)
                    
                    # Determine video quality settings
                    if usage_tier == "premium":
                        resolution = "1080:1920"  # Full HD vertical
                        crf = 18  # High quality
                        preset = "medium"
                    elif usage_tier == "free_high":
                        resolution = "1080:1920"  # Full HD vertical  
                        crf = 20  # Good quality
                        preset = "medium"
                    else:
                        resolution = "720:1280"   # HD vertical
                        crf = 23  # Standard quality
                        preset = "fast"
                    
                    # Build FFmpeg filter chain
                    input_video = ffmpeg.input(video_path, ss=segment.start_time, t=segment.duration)
                    
                    # Video processing pipeline
                    video = input_video.video
                    
                    # Scale and format for social media (vertical)
                    video = video.filter('scale', resolution, force_original_aspect_ratio='decrease')
                    video = video.filter('pad', resolution.replace(':', ':'), '(ow-iw)/2', '(oh-ih)/2', 'black')
                    
                    # Add professional effects for premium tiers
                    if quality_config["video_effects"]:
                        # Add subtle color enhancement
                        video = video.filter('eq', contrast=1.1, brightness=0.05, saturation=1.15)
                        
                        # Add fade effects
                        video = video.filter('fade', type='in', duration=0.3)
                        video = video.filter('fade', type='out', start_time=segment.duration-0.3, duration=0.3)
                    
                    # Add professional subtitles
                    if subtitle_file and os.path.exists(subtitle_file):
                        # Advanced subtitle styling based on tier
                        if usage_tier == "premium":
                            subtitle_style = "FontName=Arial Black,FontSize=32,PrimaryColour=&H00FFFFFF,SecondaryColour=&H00000000,OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Italic=0,Underline=0,StrikeOut=0,ScaleX=100,ScaleY=100,Spacing=0,Angle=0,BorderStyle=1,Outline=3,Shadow=2,Alignment=2,MarginL=10,MarginR=10,MarginV=20"
                        elif usage_tier == "free_high":
                            subtitle_style = "FontName=Arial,FontSize=28,PrimaryColour=&H00FFFFFF,SecondaryColour=&H00000000,OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Outline=2,Shadow=2,Alignment=2,MarginV=30"
                        else:
                            subtitle_style = "FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,Bold=1,Outline=1,Alignment=2,MarginV=40"
                        
                        video = video.filter('subtitles', subtitle_file, force_style=subtitle_style)
                    
                    # Audio processing
                    audio = input_video.audio
                    if quality_config["video_effects"]:
                        # Audio enhancement for premium
                        audio = audio.filter('volume', '1.1')  # Slight volume boost
                        audio = audio.filter('highpass', f=80)  # Remove low-frequency noise
                    
                    # Output final video
                    output = ffmpeg.output(
                        video, audio, output_path,
                        vcodec='libx264',
                        acodec='aac',
                        crf=crf,
                        preset=preset,
                        movflags='faststart',  # Optimize for web playback
                        pix_fmt='yuv420p'     # Ensure compatibility
                    )
                    
                    # Run FFmpeg
                    ffmpeg.run(output, overwrite_output=True, quiet=True)
                    
                    # Verify output
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        final_clips.append(output_path)
                        logger.info(f"✅ Created professional clip: {output_path} ({usage_tier} quality)")
                    else:
                        logger.error(f"❌ Failed to create clip: {output_path}")
                    
                    # Cleanup subtitle file
                    if subtitle_file and os.path.exists(subtitle_file):
                        os.remove(subtitle_file)
                
                except Exception as e:
                    logger.error(f"Error creating clip for segment {segment.id}: {str(e)}")
                    continue
            
            logger.info(f"🎬 Created {len(final_clips)} professional clips ({usage_tier} tier)")
            return final_clips
            
        except Exception as e:
            logger.error(f"Error in professional clip creation: {str(e)}")
            return []
    
    async def _create_subtitle_file(self, segment: VideoSegment, usage_tier: str) -> str:
        """Create professional SRT subtitle file"""
        try:
            subtitle_content = segment.subtitle_content
            
            # If no subtitle content, generate based on caption
            if not subtitle_content and segment.caption_text:
                if usage_tier in ["premium", "free_high"]:
                    # Generate multi-line subtitles for premium
                    lines = self._split_text_for_subtitles(segment.caption_text, 35)
                    subtitle_content = ""
                    
                    line_duration = segment.duration / len(lines) if lines else segment.duration
                    for i, line in enumerate(lines):
                        start_time = i * line_duration
                        end_time = min((i + 1) * line_duration, segment.duration)
                        
                        subtitle_content += f"{i + 1}\n"
                        subtitle_content += f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}\n"
                        subtitle_content += f"{line}\n\n"
                else:
                    # Simple subtitle for standard tier
                    subtitle_content = f"1\n00:00:00,000 --> {self._format_srt_time(segment.duration)}\n{segment.caption_text[:50]}\n\n"
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
                f.write(subtitle_content)
                return f.name
                
        except Exception as e:
            logger.error(f"Error creating subtitle file: {str(e)}")
            return None
    
    def _split_text_for_subtitles(self, text: str, max_length: int) -> List[str]:
        """Split text into subtitle-appropriate lines"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            if len(' '.join(current_line + [word])) <= max_length:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines[:3]  # Maximum 3 lines per subtitle