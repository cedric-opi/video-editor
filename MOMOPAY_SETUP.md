# MomoPay Integration Setup Guide 🇻🇳

This guide explains how to set up MomoPay (Vietnam's leading mobile payment platform) to receive payments for your Viral Video Analyzer application.

## 📋 Overview

MomoPay supports:
- ✅ **ATM Card Payments** - Vietnamese bank cards
- ✅ **MoMo Wallet** - Digital wallet transactions
- ✅ **Currency Support** - VND (Vietnamese Dong) and USD
- ✅ **Automatic Currency Conversion** - Real-time rates
- ✅ **Sandbox Testing** - Safe testing environment

## 🚀 Getting Started

### Step 1: Create MomoPay Business Account

1. **Visit MomoPay Business Portal**
   - Go to: https://business.momo.vn/
   - Click "Register for Business Account"

2. **Required Documents**
   - Business License (Giấy phép kinh doanh)
   - Tax Code (Mã số thuế)
   - Bank Account Information
   - Authorized Representative ID

3. **Business Information**
   - Company Name
   - Business Address
   - Contact Information
   - Expected Transaction Volume

### Step 2: Get API Credentials

Once your business account is approved, you'll receive:

1. **Partner Code** (MOMO_PARTNER_CODE)
2. **Access Key** (MOMO_ACCESS_KEY) 
3. **Secret Key** (MOMO_SECRET_KEY)

### Step 3: Configure Your Application

1. **Update Backend Environment**
   ```bash
   # Edit /app/backend/.env file
   MOMO_PARTNER_CODE=YOUR_ACTUAL_PARTNER_CODE
   MOMO_ACCESS_KEY=YOUR_ACTUAL_ACCESS_KEY
   MOMO_SECRET_KEY=YOUR_ACTUAL_SECRET_KEY
   ```

2. **Replace Sandbox Credentials**
   - Remove the current test credentials
   - Add your production credentials from MomoPay

### Step 4: Bank Account Setup for Receiving Funds

1. **Link Business Bank Account**
   - Go to MomoPay Business Dashboard
   - Navigate to "Account Settings" > "Bank Accounts"
   - Add your business bank account details

2. **Supported Vietnamese Banks**
   - Vietcombank (VCB)
   - BIDV
   - VietinBank
   - Techcombank (TCB)
   - ACB
   - MB Bank
   - Sacombank
   - And 40+ other banks

3. **Account Verification**
   - MomoPay will make a small test deposit
   - Verify the deposit amount to confirm ownership

## 💰 Payment Settlement

### Automatic Transfers
- **Frequency**: Daily or weekly (configurable)
- **Time**: Usually processed at 9:00 AM Vietnam time
- **Fees**: 1.5-2.5% per transaction + settlement fees

### Manual Withdrawals
- Available in MomoPay Business Dashboard
- Instant transfer to linked bank account
- Minimum withdrawal: 50,000 VND

## 🔒 Security Setup

### IP Whitelisting (Production)
The application is configured for these MomoPay IPs:
- **Incoming**: 210.245.113.71
- **Outgoing**: 118.69.210.244, 118.68.171.198

### Webhook Security
- All webhook calls are validated with HMAC SHA256
- Secret key is used for signature verification
- Automatic fraud detection included

## 🧪 Testing Your Integration

### Current Sandbox Mode
The application currently runs in **DEMO MODE** for testing:
- Test Partner Code: `MOMO_TEST_PARTNER`
- Test Access Key: `MOMO_TEST_ACCESS` 
- Test Secret Key: `MOMO_TEST_SECRET`

### Production Testing Checklist
Before going live, test:
- [ ] Small payment (10,000 VND)
- [ ] Premium plan purchase (240,000 VND monthly)
- [ ] ATM card payment flow
- [ ] MoMo wallet payment flow
- [ ] Refund process
- [ ] Webhook notifications

## 📊 Currency Conversion

### Automatic Conversion Rates
- **USD to VND**: ~24,000:1 (updated hourly)
- **VND to USD**: ~0.0000417:1 (updated hourly)

### Pricing Configuration
Current premium plans:
- **Monthly**: $9.99 USD = 240,000 VND
- **Yearly**: $99.99 USD = 2,400,000 VND

## 🚨 Important Notes

### Production Deployment
1. **Replace all test credentials** with real MomoPay credentials
2. **Update IP whitelist** in production environment
3. **Enable production webhook URLs** in MomoPay dashboard
4. **Set up monitoring** for payment failures

### Compliance Requirements (Vietnam)
- Register with State Bank of Vietnam if processing >1B VND/month
- Maintain transaction records for 5+ years
- Report suspicious transactions per AML requirements
- Apply proper VAT (10%) on service fees

### Customer Support
- **MomoPay Business Support**: 1900 545 441
- **Technical Support**: api-support@momo.vn
- **Documentation**: https://developers.momo.vn/

## 🔗 Integration Status

### Current Features
- ✅ Payment gateway integration
- ✅ ATM card support framework
- ✅ Currency conversion logic
- ✅ Sandbox testing environment
- ✅ Webhook security validation

### Ready for Production
Once you add your real MomoPay credentials:
- Replace test credentials in `.env` file
- Restart backend: `sudo supervisorctl restart backend`
- Test with small payment
- Monitor transaction logs

---

## 📞 Need Help?

If you encounter issues during setup:

1. **Check MomoPay Documentation**: https://developers.momo.vn/
2. **Contact MomoPay Support**: Technical integration support
3. **Verify Credentials**: Ensure all keys are correctly formatted
4. **Test Environment**: Use sandbox first before production

**Your Viral Video Analyzer is ready to accept payments in Vietnam! 🚀**

---

*Last Updated: October 2024*
*Version: 1.0 - Sandbox Ready*