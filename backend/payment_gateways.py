"""
Multi-Payment Gateway Adapter System
Supports global payment processing through multiple providers
"""

import os
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from enum import Enum

# Payment gateway imports
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse
import requests
import hmac
import hashlib
from paypalcheckoutsdk.core import SandboxEnvironment, LiveEnvironment, PayPalHttpClient
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest

logger = logging.getLogger(__name__)

class PaymentProvider(Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    MOMOPAY = "momopay"

class PaymentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PaymentRequest:
    def __init__(self, amount: float, currency: str, user_email: str, plan_type: str, 
                 success_url: str, cancel_url: str, metadata: Dict[str, Any] = None):
        self.amount = amount
        self.currency = currency
        self.user_email = user_email
        self.plan_type = plan_type
        self.success_url = success_url
        self.cancel_url = cancel_url
        self.metadata = metadata or {}

class PaymentResponse:
    def __init__(self, provider: PaymentProvider, checkout_url: str = None, 
                 session_id: str = None, order_id: str = None, status: PaymentStatus = PaymentStatus.PENDING,
                 error: str = None, raw_response: Dict[str, Any] = None):
        self.provider = provider
        self.checkout_url = checkout_url
        self.session_id = session_id
        self.order_id = order_id
        self.status = status
        self.error = error
        self.raw_response = raw_response or {}

class PaymentAdapter(ABC):
    """Abstract base class for payment adapters"""
    
    @abstractmethod
    async def create_checkout_session(self, request: PaymentRequest) -> PaymentResponse:
        pass
    
    @abstractmethod
    async def get_payment_status(self, session_id: str) -> PaymentResponse:
        pass
    
    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        pass

class StripeAdapter(PaymentAdapter):
    def __init__(self, host_url: str):
        self.webhook_url = f"{host_url}api/webhook/stripe"
        self.stripe_client = StripeCheckout(
            api_key=os.environ.get('STRIPE_API_KEY'),
            webhook_url=self.webhook_url
        )
    
    async def create_checkout_session(self, request: PaymentRequest) -> PaymentResponse:
        try:
            checkout_request = CheckoutSessionRequest(
                amount=request.amount,
                currency=request.currency,
                success_url=request.success_url,
                cancel_url=request.cancel_url,
                metadata={
                    "user_email": request.user_email,
                    "plan_type": request.plan_type,
                    "source": "viral_video_analyzer",
                    **request.metadata
                }
            )
            
            session = await self.stripe_client.create_checkout_session(checkout_request)
            
            return PaymentResponse(
                provider=PaymentProvider.STRIPE,
                checkout_url=session.url,
                session_id=session.session_id,
                status=PaymentStatus.PENDING
            )
            
        except Exception as e:
            logger.error(f"Stripe checkout creation failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.STRIPE,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def get_payment_status(self, session_id: str) -> PaymentResponse:
        try:
            status_response = await self.stripe_client.get_checkout_status(session_id)
            
            status_map = {
                "paid": PaymentStatus.COMPLETED,
                "unpaid": PaymentStatus.PENDING,
                "expired": PaymentStatus.CANCELLED
            }
            
            return PaymentResponse(
                provider=PaymentProvider.STRIPE,
                session_id=session_id,
                status=status_map.get(status_response.payment_status, PaymentStatus.PENDING),
                raw_response=status_response.__dict__
            )
            
        except Exception as e:
            logger.error(f"Stripe status check failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.STRIPE,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        try:
            signature = headers.get("Stripe-Signature")
            webhook_response = await self.stripe_client.handle_webhook(payload, signature)
            return {
                "provider": "stripe",
                "event_type": webhook_response.event_type,
                "session_id": webhook_response.session_id
            }
        except Exception as e:
            logger.error(f"Stripe webhook handling failed: {str(e)}")
            raise

class PayPalAdapter(PaymentAdapter):
    def __init__(self, host_url: str):
        self.webhook_url = f"{host_url}api/webhook/paypal"
        self.client_id = os.environ.get('PAYPAL_CLIENT_ID')
        self.client_secret = os.environ.get('PAYPAL_SECRET')
        
        # Use Sandbox for development, Live for production
        self.environment = SandboxEnvironment(
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        self.client = PayPalHttpClient(self.environment)
    
    async def create_checkout_session(self, request: PaymentRequest) -> PaymentResponse:
        try:
            order_request = OrdersCreateRequest()
            order_request.prefer('return=representation')
            
            order_request.request_body({
                "intent": "CAPTURE",
                "application_context": {
                    "return_url": request.success_url,
                    "cancel_url": request.cancel_url,
                    "brand_name": "Viral Video Analyzer",
                    "landing_page": "BILLING",
                    "user_action": "PAY_NOW"
                },
                "purchase_units": [{
                    "reference_id": f"{request.plan_type}_{request.user_email}",
                    "description": f"Premium Plan: {request.plan_type}",
                    "amount": {
                        "currency_code": request.currency.upper(),
                        "value": f"{request.amount:.2f}"
                    },
                    "custom_id": json.dumps({
                        "user_email": request.user_email,
                        "plan_type": request.plan_type,
                        **request.metadata
                    })
                }]
            })
            
            response = await self.client.execute(order_request)
            
            # Get approval URL
            approval_url = None
            for link in response.result.links:
                if link.rel == "approve":
                    approval_url = link.href
                    break
            
            return PaymentResponse(
                provider=PaymentProvider.PAYPAL,
                checkout_url=approval_url,
                order_id=response.result.id,
                status=PaymentStatus.PENDING,
                raw_response=response.result.__dict__
            )
            
        except Exception as e:
            logger.error(f"PayPal checkout creation failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.PAYPAL,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def get_payment_status(self, order_id: str) -> PaymentResponse:
        try:
            # For PayPal, we need to capture the order first
            capture_request = OrdersCaptureRequest(order_id)
            response = await self.client.execute(capture_request)
            
            status_map = {
                "COMPLETED": PaymentStatus.COMPLETED,
                "PENDING": PaymentStatus.PROCESSING,
                "DECLINED": PaymentStatus.FAILED,
                "VOIDED": PaymentStatus.CANCELLED
            }
            
            return PaymentResponse(
                provider=PaymentProvider.PAYPAL,
                order_id=order_id,
                status=status_map.get(response.result.status, PaymentStatus.PENDING),
                raw_response=response.result.__dict__
            )
            
        except Exception as e:
            logger.error(f"PayPal status check failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.PAYPAL,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        try:
            # PayPal webhook verification would go here
            event_type = payload.get("event_type", "")
            resource = payload.get("resource", {})
            
            return {
                "provider": "paypal",
                "event_type": event_type,
                "order_id": resource.get("id"),
                "status": resource.get("status")
            }
        except Exception as e:
            logger.error(f"PayPal webhook handling failed: {str(e)}")
            raise

class MomoPayAdapter(PaymentAdapter):
    def __init__(self, host_url: str):
        self.webhook_url = f"{host_url}api/webhook/momopay"
        self.partner_code = os.environ.get('MOMO_PARTNER_CODE')
        self.access_key = os.environ.get('MOMO_ACCESS_KEY')
        self.secret_key = os.environ.get('MOMO_SECRET_KEY')
        self.endpoint = "https://test-payment.momo.vn/v2/gateway/api/create"
        self.atm_endpoint = "https://test-payment.momo.vn/v2/gateway/api/atm/create"
        self.query_endpoint = "https://test-payment.momo.vn/v2/gateway/api/query"
        
        # IP whitelist for security
        self.allowed_incoming_ips = ["210.245.113.71"]
        self.allowed_outgoing_ips = ["118.69.210.244", "118.68.171.198"]
    
    def generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for MomoPay requests"""
        raw_signature = "&".join([f"{k}={v}" for k, v in sorted(data.items())])
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def get_live_exchange_rate(self) -> float:
        """Get live USD to VND exchange rate with fallback"""
        try:
            # Try to get live rates from exchange API
            response = requests.get(
                "https://api.exchangerate-api.com/v4/latest/USD",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                vnd_rate = data.get("rates", {}).get("VND")
                if vnd_rate:
                    logger.info(f"💱 Live exchange rate: 1 USD = {vnd_rate} VND")
                    return float(vnd_rate)
        except Exception as e:
            logger.warning(f"Failed to fetch live exchange rate: {str(e)}")
        
        # Fallback to configured rate
        fallback_rate = 24000
        logger.info(f"💱 Using fallback exchange rate: 1 USD = {fallback_rate} VND")
        return fallback_rate
    
    def validate_webhook_ip(self, client_ip: str) -> bool:
        """Validate that webhook request comes from authorized MomoPay IPs"""
        return client_ip in self.allowed_incoming_ips
    
    async def create_atm_payment(self, request: PaymentRequest, bank_code: str = None) -> PaymentResponse:
        """Create ATM card payment specifically"""
        try:
            # Get live exchange rate
            exchange_rate = await self.get_live_exchange_rate()
            amount_vnd = int(request.amount * exchange_rate)
            
            request_id = str(uuid.uuid4())
            order_id = f"ATM_{request.plan_type}_{int(time.time())}"
            
            # Enhanced ATM payment data
            request_data = {
                "partnerCode": self.partner_code,
                "partnerName": "Viral Video Analyzer",
                "storeId": "ViralVideoStore",
                "requestId": request_id,
                "amount": amount_vnd,
                "orderId": order_id,
                "orderInfo": f"Premium Plan ATM Payment: {request.plan_type}",
                "redirectUrl": request.success_url.replace("{CHECKOUT_SESSION_ID}", request_id).replace("{PROVIDER}", "momopay_atm"),
                "ipnUrl": self.webhook_url,
                "lang": "vi",  # Vietnamese for ATM users
                "extraData": json.dumps({
                    "user_email": request.user_email,
                    "plan_type": request.plan_type,
                    "payment_method": "atm",
                    "exchange_rate": exchange_rate,
                    "original_amount_usd": request.amount,
                    **request.metadata
                }),
                "requestType": "payWithMoMoATM",
                "autoCapture": True,  # Auto-capture for ATM payments
            }
            
            # Add bank code if specified
            if bank_code:
                request_data["bankCode"] = bank_code
            
            # Generate signature
            signature_data = {
                "accessKey": self.access_key,
                "amount": str(amount_vnd),
                "extraData": request_data["extraData"],
                "ipnUrl": self.webhook_url,
                "orderId": order_id,
                "orderInfo": request_data["orderInfo"],
                "partnerCode": self.partner_code,
                "redirectUrl": request_data["redirectUrl"],
                "requestId": request_id,
                "requestType": "payWithMoMoATM"
            }
            
            if bank_code:
                signature_data["bankCode"] = bank_code
            
            request_data["signature"] = self.generate_signature(signature_data)
            
            # Use ATM-specific endpoint
            response = requests.post(
                self.atm_endpoint,
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("resultCode") == 0:
                logger.info(f"✅ ATM payment created: {order_id} - {amount_vnd} VND (${request.amount} USD)")
                return PaymentResponse(
                    provider=PaymentProvider.MOMOPAY,
                    checkout_url=result.get("payUrl"),
                    session_id=request_id,
                    order_id=order_id,
                    status=PaymentStatus.PENDING,
                    raw_response=result
                )
            else:
                return PaymentResponse(
                    provider=PaymentProvider.MOMOPAY,
                    status=PaymentStatus.FAILED,
                    error=f"ATM payment failed: {result.get('message', 'Unknown error')}"
                )
                
        except Exception as e:
            logger.error(f"ATM payment creation failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.MOMOPAY,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def create_checkout_session(self, request: PaymentRequest) -> PaymentResponse:
        try:
            # Get live exchange rate for accurate conversion
            exchange_rate = await self.get_live_exchange_rate()
            amount_vnd = int(request.amount * exchange_rate)
            request_id = str(uuid.uuid4())
            order_id = f"MOMO_{request.plan_type}_{int(time.time())}"
            
            # MomoPay request data
            request_data = {
                "partnerCode": self.partner_code,
                "partnerName": "Viral Video Analyzer",
                "storeId": "ViralVideoStore",
                "requestId": request_id,
                "amount": amount_vnd,
                "orderId": order_id,
                "orderInfo": f"Premium Plan: {request.plan_type}",
                "redirectUrl": request.success_url.replace("{CHECKOUT_SESSION_ID}", request_id).replace("{PROVIDER}", "momopay"),
                "ipnUrl": self.webhook_url,
                "lang": "en",  # Use English for international users
                "extraData": json.dumps({
                    "user_email": request.user_email,
                    "plan_type": request.plan_type,
                    "payment_method": "momo_wallet", 
                    "exchange_rate": exchange_rate,
                    "original_amount_usd": request.amount,
                    **request.metadata
                }),
                "requestType": "payWithMoMoATM",  # Support both wallet and ATM
            }
            
            # Generate signature for authentication
            signature_data = {
                "accessKey": self.access_key,
                "amount": str(amount_vnd),
                "extraData": request_data["extraData"],
                "ipnUrl": self.webhook_url,
                "orderId": order_id,
                "orderInfo": request_data["orderInfo"],
                "partnerCode": self.partner_code,
                "redirectUrl": request_data["redirectUrl"],
                "requestId": request_id,
                "requestType": "payWithMoMoATM"
            }
            
            request_data["signature"] = self.generate_signature(signature_data)
            
            # Make request to MomoPay API
            response = requests.post(
                self.endpoint,
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("resultCode") == 0:
                return PaymentResponse(
                    provider=PaymentProvider.MOMOPAY,
                    checkout_url=result.get("payUrl"),
                    session_id=request_id,
                    order_id=order_id,
                    status=PaymentStatus.PENDING,
                    raw_response=result
                )
            else:
                return PaymentResponse(
                    provider=PaymentProvider.MOMOPAY,
                    status=PaymentStatus.FAILED,
                    error=f"MomoPay error: {result.get('message', 'Unknown error')}"
                )
            
        except Exception as e:
            logger.error(f"MomoPay order creation failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.MOMOPAY,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def get_payment_status(self, order_id: str) -> PaymentResponse:
        try:
            request_id = str(uuid.uuid4())
            
            # MomoPay status query data
            status_data = {
                "partnerCode": self.partner_code,
                "requestId": request_id,
                "orderId": order_id,
                "lang": "en"
            }
            
            # Generate signature for status query
            signature_data = {
                "accessKey": self.access_key,
                "orderId": order_id,
                "partnerCode": self.partner_code,
                "requestId": request_id
            }
            
            status_data["signature"] = self.generate_signature(signature_data)
            
            # Query payment status
            response = requests.post(
                "https://test-payment.momo.vn/v2/gateway/api/query",
                json=status_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # Map MomoPay result codes to payment status
            status_map = {
                0: PaymentStatus.COMPLETED,     # Success
                9000: PaymentStatus.PROCESSING, # Transaction is being processed
                1000: PaymentStatus.FAILED,     # Transaction failed
                1001: PaymentStatus.FAILED,     # Transaction failed
                1002: PaymentStatus.FAILED,     # Transaction rejected by issuer
                1003: PaymentStatus.CANCELLED,  # Transaction cancelled by user
                1004: PaymentStatus.FAILED,     # Transaction failed due to insufficient funds
                1005: PaymentStatus.FAILED,     # Transaction failed due to wrong format
                1006: PaymentStatus.FAILED,     # Transaction failed due to expired
            }
            
            return PaymentResponse(
                provider=PaymentProvider.MOMOPAY,
                session_id=order_id,
                status=status_map.get(result.get("resultCode"), PaymentStatus.PENDING),
                raw_response=result
            )
            
        except Exception as e:
            logger.error(f"MomoPay status check failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.MOMOPAY,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        try:
            # Verify MomoPay webhook signature
            signature = headers.get("signature", "")
            
            # Generate expected signature for verification
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
                raise ValueError("Invalid webhook signature")
            
            return {
                "provider": "momopay",
                "event_type": "payment_status_update",
                "order_id": payload.get("orderId"),
                "result_code": payload.get("resultCode"),
                "transaction_id": payload.get("transId"),
                "status": "completed" if payload.get("resultCode") == 0 else "failed"
            }
            
        except Exception as e:
            logger.error(f"MomoPay webhook handling failed: {str(e)}")
            raise

class PaymentGatewayManager:
    """Manages multiple payment gateways and routes requests based on region/preference"""
    
    def __init__(self, host_url: str):
        self.host_url = host_url
        self.adapters = {
            PaymentProvider.STRIPE: StripeAdapter(host_url),
            PaymentProvider.PAYPAL: PayPalAdapter(host_url),
            PaymentProvider.MOMOPAY: MomoPayAdapter(host_url)
        }
        
        # Regional preferences for payment providers
        self.regional_preferences = {
            "default": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "US": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "CA": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "GB": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "EU": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "VN": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
            "TH": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL],
            "LA": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL],
            "KH": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL],
            "MM": [PaymentProvider.MOMOPAY, PaymentProvider.PAYPAL],
            "SG": [PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
            "MY": [PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
            "ID": [PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
            "PH": [PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
            # Add more regions as needed
        }
    
    def get_available_providers(self, region: str = None) -> list:
        """Get available payment providers for a region"""
        if region and region.upper() in self.regional_preferences:
            return self.regional_preferences[region.upper()]
        return self.regional_preferences["default"]
    
    async def create_payment(self, request: PaymentRequest, provider: PaymentProvider = None, 
                           region: str = None) -> PaymentResponse:
        """Create payment using specified or auto-selected provider"""
        try:
            if not provider:
                # Auto-select based on region
                available_providers = self.get_available_providers(region)
                provider = available_providers[0] if available_providers else PaymentProvider.STRIPE
            
            if provider not in self.adapters:
                raise ValueError(f"Unsupported payment provider: {provider}")
            
            return await self.adapters[provider].create_checkout_session(request)
            
        except Exception as e:
            logger.error(f"Payment creation failed: {str(e)}")
            return PaymentResponse(
                provider=provider,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def get_payment_status(self, session_id: str, provider: PaymentProvider) -> PaymentResponse:
        """Get payment status from specified provider"""
        try:
            if provider not in self.adapters:
                raise ValueError(f"Unsupported payment provider: {provider}")
            
            return await self.adapters[provider].get_payment_status(session_id)
            
        except Exception as e:
            logger.error(f"Payment status check failed: {str(e)}")
            return PaymentResponse(
                provider=provider,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def handle_webhook(self, provider: PaymentProvider, payload: Dict[str, Any], 
                           headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle webhook from specified provider"""
        if provider not in self.adapters:
            raise ValueError(f"Unsupported payment provider: {provider}")
        
        return await self.adapters[provider].handle_webhook(payload, headers)