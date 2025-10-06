# 🚀 Viral Video Analyzer - Million Dollar System

**AI-powered viral video analysis and segmentation system with global payment processing**

![System Status](https://img.shields.io/badge/Status-Production%20Ready-green)
![AI Engine](https://img.shields.io/badge/AI-GPT--4%20Enhanced-blue)
![Payments](https://img.shields.io/badge/Payments-Global%20Coverage-purple)

## 🎯 System Overview

Transform any video into viral-ready content with:
- **🤖 Advanced AI Analysis**: Identifies viral techniques and engagement factors
- **✂️ Smart Segmentation**: Creates max 3 optimized clips for long videos (5+ min)
- **📝 Embedded Subtitles**: Professional captions burned into video
- **💰 Global Payments**: MomoPay, PayPal, Stripe integration
- **🌍 Multi-Region Support**: Optimized for Vietnam and worldwide

## 🏗️ Architecture

```
/backend/
├── server.py              # Main FastAPI application
├── config.py              # Configuration settings
├── database.py            # MongoDB connection
├── models.py              # Data models
├── payment_gateways.py    # Multi-gateway payment system
└── services/
    ├── user_service.py     # User management & premium status
    ├── payment_service.py  # MomoPay integration
    └── video_service.py    # AI video processing

/frontend/
├── src/
│   ├── App.js             # Main React application
│   ├── components/        # UI components
│   └── services/          # API services
```

## ⚙️ Environment Setup

### Required Environment Variables

Create `/app/backend/.env` with the following:

```bash
# Database Configuration
MONGO_URL="mongodb://localhost:27017"
DB_NAME="viral_video_analyzer"
CORS_ORIGINS="*"

# AI Configuration  
OPENAI_API_KEY=your_openai_api_key_here

# Payment Gateway Configuration
STRIPE_API_KEY=your_stripe_key_here
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_SECRET=your_paypal_secret

# MomoPay Configuration (Vietnam Market)
MOMO_PARTNER_CODE=your_momo_partner_code
MOMO_ACCESS_KEY=your_momo_access_key  
MOMO_SECRET_KEY=your_momo_secret_key
MOMO_ENVIRONMENT=sandbox  # or 'production'
```

### Frontend Environment

Create `/app/frontend/.env` with:

```bash
REACT_APP_BACKEND_URL=https://your-domain.com
```

## 💳 MomoPay Integration Setup

### Step 1: Get MomoPay Credentials

**For Sandbox Testing:**
1. Visit [MomoPay Developer Portal](https://developers.momo.vn)
2. Register for sandbox account
3. Complete merchant verification
4. Get your credentials:
   - Partner Code
   - Access Key  
   - Secret Key

**For Production:**
1. Complete MomoPay merchant registration
2. Submit business verification documents
3. Get production credentials
4. Update IP whitelist: `210.245.113.71` (incoming), `118.69.210.244`, `118.68.171.198` (outgoing)

### Step 2: Configure MomoPay Credentials

**Option A: Environment Variables (Recommended)**
```bash
# Add to /app/backend/.env
MOMO_PARTNER_CODE=MOMOXXX123
MOMO_ACCESS_KEY=XXXXXXXXXXXXXX  
MOMO_SECRET_KEY=XXXXXXXXXXXXXX
MOMO_ENVIRONMENT=sandbox  # Change to 'production' for live
```

**Option B: Direct Configuration**
```bash
# Update /app/backend/config.py
MOMO_PARTNER_CODE = "your_partner_code_here"
MOMO_ACCESS_KEY = "your_access_key_here"
MOMO_SECRET_KEY = "your_secret_key_here"
```

### Step 3: Test MomoPay Integration

```bash
# Test payment creation
curl -X POST https://your-domain.com/api/create-checkout \
  -H "Content-Type: application/json" \
  -d '{
    "plan_type": "premium_monthly",
    "user_email": "test@vietnam.com",
    "origin_url": "https://your-domain.com",
    "payment_provider": "momopay",
    "currency": "VND",
    "user_region": "VN"
  }'
```

### Step 4: Webhook Configuration

Set your MomoPay webhook URL to:
```
https://your-domain.com/api/webhook/momopay
```

## 🚀 Getting Started

### Development
```bash
# Start backend
cd /app/backend
python server.py

# Start frontend  
cd /app/frontend
npm start
```

### Production
```bash
# Using supervisor (recommended)
sudo supervisorctl restart all

# Check status
sudo supervisorctl status
```

## 🔧 Troubleshooting

### Common Issues

**MomoPay Authentication Failed (resultCode: 13)**
```bash
# Check credentials
echo $MOMO_PARTNER_CODE
echo $MOMO_ACCESS_KEY

# Verify environment
grep MOMO /app/backend/.env
```

**Video Processing Fails**
```bash
# Check OpenAI API key
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# Check ffmpeg installation
ffmpeg -version
```

## 🎯 Business Model

### Freemium Strategy
- **Free**: 2 high-quality videos, then standard quality
- **Premium Monthly**: $9.99 (240,000 VND) - Unlimited high-quality
- **Premium Yearly**: $99.99 (2,400,000 VND) - 2 months free

---

**🎉 Your Million-Dollar Viral Video System is Ready!**
