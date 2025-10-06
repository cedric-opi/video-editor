"""
Enhanced MomoPay Payment Service with proper Vietnamese integration
"""
import os
import json
import hmac
import hashlib
import uuid
import time
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from config import (
    MOMO_PARTNER_CODE, MOMO_ACCESS_KEY, MOMO_SECRET_KEY,
    MOMO_ENDPOINT, MOMO_QUERY_ENDPOINT, USD_TO_VND_RATE, VND_TO_USD_RATE
)
from database import get_database
from models import PaymentTransaction
from services.user_service import UserService

logger = logging.getLogger(__name__)

class MomoPayService:
    
    def __init__(self):
        self.partner_code = MOMO_PARTNER_CODE
        self.access_key = MOMO_ACCESS_KEY
        self.secret_key = MOMO_SECRET_KEY
        self.endpoint = MOMO_ENDPOINT
        self.query_endpoint = MOMO_QUERY_ENDPOINT
        
        # Demo mode for testing when credentials are not available
        self.demo_mode = (
            self.partner_code in ["MOMO_SANDBOX_PARTNER", "MOMO_TEST_PARTNER", None] or
            self.access_key in ["MOMO_SANDBOX_ACCESS", "MOMO_TEST_ACCESS", None] or
            self.secret_key in ["MOMO_SANDBOX_SECRET", "MOMO_TEST_SECRET", None]
        )
        
        if self.demo_mode:
            logger.info("🧪 MomoPay running in DEMO MODE - payments will be simulated")
        
        # Supported Vietnamese banks for ATM payments
        self.atm_banks = [
            {"code": "VIETCOMBANK", "name": "Vietcombank", "display": "Ngân hàng TMCP Ngoại thương Việt Nam"},
            {"code": "BIDV", "name": "BIDV", "display": "Ngân hàng TMCP Đầu tư và Phát triển Việt Nam"},
            {"code": "VIETINBANK", "name": "VietinBank", "display": "Ngân hàng TMCP Công thương Việt Nam"},
            {"code": "TECHCOMBANK", "name": "Techcombank", "display": "Ngân hàng TMCP Kỹ thương Việt Nam"},
            {"code": "ACB", "name": "ACB", "display": "Ngân hàng TMCP Á Châu"},
            {"code": "MB", "name": "MB Bank", "display": "Ngân hàng TMCP Quân đội"},
            {"code": "SACOMBANK", "name": "Sacombank", "display": "Ngân hàng TMCP Sài Gòn Thương tín"},
            {"code": "AGRIBANK", "name": "Agribank", "display": "Ngân hàng NN&PTNT Việt Nam"},
            {"code": "VPBANK", "name": "VPBank", "display": "Ngân hàng TMCP Việt Nam Thịnh vượng"},
            {"code": "TPB", "name": "TPBank", "display": "Ngân hàng TMCP Tiên Phong"}
        ]
    
    async def get_live_exchange_rate(self) -> Dict[str, float]:
        """Get live exchange rates with fallback"""
        try:
            response = requests.get(
                "https://api.exchangerate-api.com/v4/latest/USD",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                vnd_rate = data.get("rates", {}).get("VND", USD_TO_VND_RATE)
                usd_rate = 1.0 / vnd_rate if vnd_rate else VND_TO_USD_RATE
                
                logger.info(f"💱 Live rates: 1 USD = {vnd_rate:.0f} VND")
                return {"usd_to_vnd": vnd_rate, "vnd_to_usd": usd_rate}
        except Exception as e:
            logger.warning(f"Exchange rate API failed: {str(e)}")
        
        # Fallback rates
        return {"usd_to_vnd": USD_TO_VND_RATE, "vnd_to_usd": VND_TO_USD_RATE}
    
    def get_supported_atm_banks(self) -> list:
        """Get list of supported Vietnamese banks for ATM payments"""
        return self.atm_banks
    
    def generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for MomoPay requests"""
        try:
            # Create raw signature string from sorted parameters
            raw_signature = "&".join([f"{k}={v}" for k, v in sorted(data.items())])
            
            # Generate HMAC-SHA256 signature
            signature = hmac.new(
                self.secret_key.encode('utf-8'),
                raw_signature.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
        except Exception as e:
            logger.error(f"Error generating MomoPay signature: {e}")
            raise
    
    def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert between USD and VND"""
        if from_currency.upper() == to_currency.upper():
            return amount
        
        if from_currency.upper() == "USD" and to_currency.upper() == "VND":
            return amount * USD_TO_VND_RATE
        elif from_currency.upper() == "VND" and to_currency.upper() == "USD":
            return amount * VND_TO_USD_RATE
        else:
            raise ValueError(f"Unsupported currency conversion: {from_currency} to {to_currency}")
    
    async def create_payment(self, user_email: str, plan_type: str, amount: float, 
                           currency: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """Create MomoPay payment request"""
        try:
            # 🧪 DEMO MODE: Simulate successful payment for testing
            if self.demo_mode:
                return await self._create_demo_payment(user_email, plan_type, amount, currency, success_url)
            # Convert amount to VND if needed
            if currency.upper() == "USD":
                amount_vnd = int(self.convert_currency(amount, "USD", "VND"))
                display_currency = "VND"
            else:
                amount_vnd = int(amount)
                display_currency = "VND"
            
            # Generate unique IDs
            request_id = str(uuid.uuid4())
            order_id = f"VVA_{plan_type.upper()}_{int(time.time())}"
            
            # Prepare success and cancel URLs
            success_url_formatted = success_url.replace("{CHECKOUT_SESSION_ID}", request_id).replace("{PROVIDER}", "momopay")
            cancel_url_formatted = cancel_url
            
            # MomoPay payment request data
            request_data = {
                "partnerCode": self.partner_code,
                "partnerName": "Viral Video Analyzer",
                "storeId": "VVA_STORE",
                "requestId": request_id,
                "amount": amount_vnd,
                "orderId": order_id,
                "orderInfo": f"Upgrade to {plan_type.replace('_', ' ').title()} - Viral Video Analyzer Premium",
                "redirectUrl": success_url_formatted,
                "ipnUrl": f"https://videditor-pro-3.preview.emergentagent.com/api/webhook/momopay",
                "lang": "en",
                "extraData": json.dumps({
                    "user_email": user_email,
                    "plan_type": plan_type,
                    "original_amount": amount,
                    "original_currency": currency,
                    "source": "viral_video_analyzer"
                }, ensure_ascii=False),
                "requestType": "payWithATM",  # ATM card payment as requested
                "autoCapture": True,
                "orderGroupId": ""
            }
            
            # Create signature data (must match MomoPay documentation order)
            signature_data = {
                "accessKey": self.access_key,
                "amount": str(amount_vnd),
                "extraData": request_data["extraData"],
                "ipnUrl": request_data["ipnUrl"],
                "orderId": order_id,
                "orderInfo": request_data["orderInfo"],
                "partnerCode": self.partner_code,
                "redirectUrl": request_data["redirectUrl"],
                "requestId": request_id,
                "requestType": "payWithATM"
            }
            
            # Generate signature
            request_data["signature"] = self.generate_signature(signature_data)
            
            logger.info(f"Creating MomoPay payment request for order: {order_id}")
            
            # Make request to MomoPay API
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ViralVideoAnalyzer/1.0"
            }
            
            response = requests.post(
                self.endpoint,
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            logger.info(f"MomoPay API Response Status: {response.status_code}")
            logger.info(f"MomoPay API Response: {response.text}")
            
            if response.status_code != 200:
                raise Exception(f"MomoPay API returned status {response.status_code}: {response.text}")
            
            result = response.json()
            
            # Check MomoPay response
            if result.get("resultCode") == 0:
                # Save transaction to database
                db = await get_database()
                transaction = PaymentTransaction(
                    user_email=user_email,
                    amount=amount,
                    currency=currency,
                    plan_type=plan_type,
                    payment_provider="momopay",
                    session_id=request_id,
                    payment_status="pending",
                    status="initiated",
                    metadata={
                        "order_id": order_id,
                        "amount_vnd": amount_vnd,
                        "momo_response": result,
                        "request_data": request_data
                    }
                )
                await db.payment_transactions.insert_one(transaction.dict())
                
                return {
                    "success": True,
                    "checkout_url": result.get("payUrl"),
                    "session_id": request_id,
                    "order_id": order_id,
                    "amount_vnd": amount_vnd,
                    "amount_usd": amount,
                    "qr_code_url": result.get("qrCodeUrl"),
                    "deep_link": result.get("deeplink"),
                    "provider": "momopay"
                }
            else:
                error_msg = result.get("message", "Unknown MomoPay error")
                logger.error(f"MomoPay error: {result.get('resultCode')} - {error_msg}")
                return {
                    "success": False,
                    "error": f"MomoPay error: {error_msg}",
                    "error_code": result.get("resultCode")
                }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error with MomoPay API: {e}")
            return {
                "success": False,
                "error": f"Payment gateway connection failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error creating MomoPay payment: {e}")
            return {
                "success": False,
                "error": f"Payment creation failed: {str(e)}"
            }
    
    async def _create_demo_payment(self, user_email: str, plan_type: str, amount: float, 
                                 currency: str, success_url: str) -> Dict[str, Any]:
        """Create demo payment for testing purposes"""
        try:
            # Generate demo IDs
            request_id = f"demo_{str(uuid.uuid4())[:8]}"
            order_id = f"DEMO_VVA_{plan_type.upper()}_{int(time.time())}"
            
            # Convert to VND if needed
            if currency.upper() == "USD":
                amount_vnd = int(self.convert_currency(amount, "USD", "VND"))
            else:
                amount_vnd = int(amount)
            
            # Save demo transaction
            db = await get_database()
            transaction = PaymentTransaction(
                user_email=user_email,
                amount=amount,
                currency=currency,
                plan_type=plan_type,
                payment_provider="momopay",
                session_id=request_id,
                payment_status="pending",
                status="initiated",
                metadata={
                    "order_id": order_id,
                    "amount_vnd": amount_vnd,
                    "demo_mode": True,
                    "demo_payment_url": f"https://demo-payment.momo.vn/pay?order={order_id}"
                }
            )
            await db.payment_transactions.insert_one(transaction.dict())
            
            # Create demo success URL
            demo_success_url = success_url.replace("{CHECKOUT_SESSION_ID}", request_id).replace("{PROVIDER}", "momopay")
            
            logger.info(f"🧪 DEMO: Created MomoPay payment simulation for {order_id}")
            
            return {
                "success": True,
                "checkout_url": f"https://demo.captivator.preview.emergentagent.com/demo-payment?order_id={order_id}&amount={amount_vnd}&currency={currency}&success_url={demo_success_url}",
                "session_id": request_id,
                "order_id": order_id,
                "amount_vnd": amount_vnd,
                "amount_usd": amount,
                "qr_code_url": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=DEMO_MOMO_PAY_{order_id}",
                "demo_mode": True,
                "provider": "momopay"
            }
            
        except Exception as e:
            logger.error(f"Demo payment creation error: {e}")
            return {"success": False, "error": f"Demo payment failed: {str(e)}"}

    async def check_payment_status(self, order_id: str) -> Dict[str, Any]:
        """Check payment status with MomoPay"""
        try:
            # 🧪 DEMO MODE: Simulate payment status check
            if self.demo_mode or order_id.startswith("DEMO_"):
                return await self._check_demo_payment_status(order_id)
            request_id = str(uuid.uuid4())
            
            # Prepare status query request
            query_data = {
                "partnerCode": self.partner_code,
                "requestId": request_id,
                "orderId": order_id,
                "lang": "en"
            }
            
            # Create signature for status query
            signature_data = {
                "accessKey": self.access_key,
                "orderId": order_id,
                "partnerCode": self.partner_code,
                "requestId": request_id
            }
            
            query_data["signature"] = self.generate_signature(signature_data)
            
            # Make status query request
            response = requests.post(
                self.query_endpoint,
                json=query_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            result = response.json()
            
            # Map MomoPay result codes to standard status
            status_mapping = {
                0: "completed",      # Success
                9000: "processing",  # Transaction processing
                1000: "failed",      # Transaction failed
                1001: "failed",      # Transaction failed
                1002: "failed",      # Transaction rejected
                1003: "cancelled",   # Transaction cancelled
                1004: "failed",      # Insufficient funds
                1005: "failed",      # Invalid format
                1006: "failed",      # Transaction expired
                8000: "cancelled",   # User cancelled
                7000: "failed",      # Debit unsuccessful
                7002: "failed",      # Payment denied
            }
            
            result_code = result.get("resultCode")
            payment_status = status_mapping.get(result_code, "pending")
            
            return {
                "success": True,
                "payment_status": payment_status,
                "result_code": result_code,
                "message": result.get("message", ""),
                "transaction_id": result.get("transId"),
                "amount": result.get("amount"),
                "raw_response": result
            }
            
        except Exception as e:
            logger.error(f"Error checking MomoPay payment status: {e}")
            return {
                "success": False,
                "error": str(e),
                "payment_status": "error"
            }
    
    async def _check_demo_payment_status(self, order_id: str) -> Dict[str, Any]:
        """Check demo payment status"""
        try:
            # Simulate payment completion after 30 seconds
            db = await get_database()
            transaction = await db.payment_transactions.find_one({
                "metadata.order_id": order_id
            })
            
            if not transaction:
                return {"success": False, "error": "Demo transaction not found", "payment_status": "error"}
            
            # Simulate payment completion based on time
            created_at = transaction.get("created_at")
            if created_at:
                time_diff = (datetime.now(timezone.utc) - created_at).total_seconds()
                if time_diff > 30:  # Auto-complete after 30 seconds
                    payment_status = "completed"
                else:
                    payment_status = "processing"
            else:
                payment_status = "processing"
            
            logger.info(f"🧪 DEMO: Payment status for {order_id}: {payment_status}")
            
            return {
                "success": True,
                "payment_status": payment_status,
                "result_code": 0 if payment_status == "completed" else 9000,
                "message": "Demo payment simulation",
                "transaction_id": f"demo_txn_{order_id[-8:]}",
                "amount": transaction.get("amount", 0),
                "raw_response": {
                    "demo_mode": True,
                    "order_id": order_id,
                    "status": payment_status
                }
            }
            
        except Exception as e:
            logger.error(f"Demo status check error: {e}")
            return {"success": False, "error": str(e), "payment_status": "error"}
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MomoPay IPN (Instant Payment Notification) webhook"""
        try:
            # Verify webhook signature
            signature = payload.get("signature", "")
            
            # Reconstruct signature data for verification
            signature_data = {
                "accessKey": self.access_key,
                "amount": str(payload.get("amount", "")),
                "extraData": payload.get("extraData", ""),
                "message": payload.get("message", ""),
                "orderId": payload.get("orderId", ""),
                "orderInfo": payload.get("orderInfo", ""),
                "orderType": payload.get("orderType", ""),
                "partnerCode": payload.get("partnerCode", ""),
                "payType": payload.get("payType", ""),
                "requestId": payload.get("requestId", ""),
                "responseTime": str(payload.get("responseTime", "")),
                "resultCode": str(payload.get("resultCode", "")),
                "transId": str(payload.get("transId", ""))
            }
            
            expected_signature = self.generate_signature(signature_data)
            
            if not hmac.compare_digest(expected_signature, signature):
                logger.warning("Invalid MomoPay webhook signature")
                return {"success": False, "error": "Invalid signature"}
            
            # Process webhook based on result code
            result_code = payload.get("resultCode")
            order_id = payload.get("orderId")
            
            if result_code == 0:  # Payment successful
                # Update payment transaction in database
                db = await get_database()
                
                # Find transaction by order_id in metadata
                transaction = await db.payment_transactions.find_one({
                    "metadata.order_id": order_id
                })
                
                if transaction and transaction["payment_status"] != "completed":
                    # Update transaction status
                    await db.payment_transactions.update_one(
                        {"_id": transaction["_id"]},
                        {"$set": {
                            "payment_status": "completed",
                            "status": "completed",
                            "metadata.webhook_data": payload,
                            "metadata.transaction_id": payload.get("transId")
                        }}
                    )
                    
                    # Activate premium plan
                    await UserService.activate_premium_plan(
                        transaction["user_email"], 
                        transaction["plan_type"]
                    )
                    
                    logger.info(f"MomoPay payment completed for order: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "result_code": result_code,
                "status": "completed" if result_code == 0 else "failed"
            }
            
        except Exception as e:
            logger.error(f"Error handling MomoPay webhook: {e}")
            return {"success": False, "error": str(e)}