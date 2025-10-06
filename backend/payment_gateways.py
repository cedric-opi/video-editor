"""
Multi-Payment Gateway Adapter System
Supports global payment processing through multiple providers
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from enum import Enum

# Payment gateway imports
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse
import razorpay
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

class RazorpayAdapter(PaymentAdapter):
    def __init__(self, host_url: str):
        self.webhook_url = f"{host_url}api/webhook/razorpay"
        self.client = razorpay.Client(auth=(
            os.environ.get('RAZORPAY_KEY_ID'),
            os.environ.get('RAZORPAY_KEY_SECRET')
        ))
    
    async def create_checkout_session(self, request: PaymentRequest) -> PaymentResponse:
        try:
            # Convert to paise (Razorpay uses smallest currency unit)
            amount_paise = int(request.amount * 100)
            
            order_data = {
                "amount": amount_paise,
                "currency": request.currency.upper(),
                "receipt": f"receipt_{request.plan_type}_{int(time.time())}",
                "notes": {
                    "user_email": request.user_email,
                    "plan_type": request.plan_type,
                    "source": "viral_video_analyzer",
                    **request.metadata
                }
            }
            
            order = self.client.order.create(data=order_data)
            
            # Razorpay doesn't have a direct checkout URL like Stripe/PayPal
            # The frontend will handle the Razorpay checkout with the order ID
            return PaymentResponse(
                provider=PaymentProvider.RAZORPAY,
                order_id=order['id'],
                status=PaymentStatus.PENDING,
                raw_response=order
            )
            
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.RAZORPAY,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def get_payment_status(self, payment_id: str) -> PaymentResponse:
        try:
            payment = self.client.payment.fetch(payment_id)
            
            status_map = {
                "captured": PaymentStatus.COMPLETED,
                "authorized": PaymentStatus.PROCESSING,
                "failed": PaymentStatus.FAILED,
                "refunded": PaymentStatus.CANCELLED
            }
            
            return PaymentResponse(
                provider=PaymentProvider.RAZORPAY,
                session_id=payment_id,
                status=status_map.get(payment['status'], PaymentStatus.PENDING),
                raw_response=payment
            )
            
        except Exception as e:
            logger.error(f"Razorpay status check failed: {str(e)}")
            return PaymentResponse(
                provider=PaymentProvider.RAZORPAY,
                status=PaymentStatus.FAILED,
                error=str(e)
            )
    
    async def handle_webhook(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        try:
            # Razorpay webhook verification
            signature = headers.get("X-Razorpay-Signature", "")
            # Note: Webhook secret verification should be implemented here
            
            event_type = payload.get("event", "")
            payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
            
            return {
                "provider": "razorpay",
                "event_type": event_type,
                "payment_id": payment.get("id"),
                "status": payment.get("status")
            }
        except Exception as e:
            logger.error(f"Razorpay webhook handling failed: {str(e)}")
            raise

class PaymentGatewayManager:
    """Manages multiple payment gateways and routes requests based on region/preference"""
    
    def __init__(self, host_url: str):
        self.host_url = host_url
        self.adapters = {
            PaymentProvider.STRIPE: StripeAdapter(host_url),
            PaymentProvider.PAYPAL: PayPalAdapter(host_url),
            PaymentProvider.RAZORPAY: RazorpayAdapter(host_url)
        }
        
        # Regional preferences for payment providers
        self.regional_preferences = {
            "default": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "US": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "CA": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "GB": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "EU": [PaymentProvider.STRIPE, PaymentProvider.PAYPAL],
            "IN": [PaymentProvider.RAZORPAY, PaymentProvider.PAYPAL, PaymentProvider.STRIPE],
            "MY": [PaymentProvider.RAZORPAY, PaymentProvider.PAYPAL],
            "SG": [PaymentProvider.RAZORPAY, PaymentProvider.PAYPAL],
            "ID": [PaymentProvider.RAZORPAY, PaymentProvider.PAYPAL],
            "TH": [PaymentProvider.RAZORPAY, PaymentProvider.PAYPAL],
            "PH": [PaymentProvider.RAZORPAY, PaymentProvider.PAYPAL],
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