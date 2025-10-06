"""
Configuration settings for the Viral Video Analyzer system
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'viral_video_analyzer')

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Payment Gateway Configuration
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')

# MomoPay Configuration
MOMO_PARTNER_CODE = os.environ.get('MOMO_PARTNER_CODE', 'MOMO_SANDBOX_PARTNER')
MOMO_ACCESS_KEY = os.environ.get('MOMO_ACCESS_KEY', 'MOMO_SANDBOX_ACCESS')
MOMO_SECRET_KEY = os.environ.get('MOMO_SECRET_KEY', 'MOMO_SANDBOX_SECRET')
MOMO_ENDPOINT = "https://test-payment.momo.vn/v2/gateway/api/create"
MOMO_QUERY_ENDPOINT = "https://test-payment.momo.vn/v2/gateway/api/query"

# MomoPay IP Whitelist for Production Security
MOMO_INCOMING_IP = "210.245.113.71"
MOMO_OUTGOING_IPS = ["118.69.210.244", "118.68.171.198"]

# MomoPay ATM Card Support
MOMO_ATM_ENDPOINT = "https://test-payment.momo.vn/v2/gateway/api/atm/create"
MOMO_ATM_BANKS = [
    "VIETCOMBANK", "BIDV", "VIETINBANK", "TECHCOMBANK", "ACB", 
    "MB", "SACOMBANK", "AGRIBANK", "VPBANK", "TPB", "SHB"
]

# Currency Conversion API
EXCHANGE_RATE_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"
FALLBACK_USD_TO_VND_RATE = 24000  # Fallback rate if API fails

# Application Configuration
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
MAX_VIDEO_DURATION_FREE = 300  # 5 minutes
MAX_VIDEO_DURATION_PREMIUM = 1800  # 30 minutes
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# Premium Plan Pricing
PREMIUM_PLANS = {
    "premium_monthly": {
        "name": "Premium Monthly",
        "price_usd": 9.99,
        "price_vnd": 240000,  # ~9.99 USD
        "description": "Upload videos up to 30 minutes, unlimited processing",
        "max_video_duration": 1800,
        "duration_days": 30
    },
    "premium_yearly": {
        "name": "Premium Yearly", 
        "price_usd": 99.99,
        "price_vnd": 2400000,  # ~99.99 USD
        "description": "Upload videos up to 30 minutes, unlimited processing + 2 months free",
        "max_video_duration": 1800,
        "duration_days": 365
    }
}

# Currency Conversion Rates (VND to USD)
VND_TO_USD_RATE = 0.0000417  # 1 VND = 0.0000417 USD (approximate)
USD_TO_VND_RATE = 24000  # 1 USD = 24,000 VND (approximate)

# Video Processing Configuration
MAX_SEGMENTS_LONG_VIDEO = 3  # Maximum segments for long videos
SEGMENT_MIN_DURATION = 10  # Minimum segment duration in seconds
SEGMENT_MAX_DURATION = 30  # Maximum segment duration in seconds

# Quality Tiers
QUALITY_TIERS = {
    "premium": {
        "max_resolution": "1080p",
        "ai_analysis_tokens": 2000,
        "caption_style": "advanced",
        "video_effects": True,
        "voice_quality": "premium"
    },
    "free_high": {
        "max_resolution": "1080p", 
        "ai_analysis_tokens": 1500,
        "caption_style": "enhanced",
        "video_effects": True,
        "voice_quality": "standard"
    },
    "standard": {
        "max_resolution": "720p",
        "ai_analysis_tokens": 800,
        "caption_style": "basic",
        "video_effects": False,
        "voice_quality": "basic"
    }
}

# Free Usage Limits
FREE_HIGH_QUALITY_VIDEOS = 2  # Number of high-quality videos for free users