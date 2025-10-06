import React, { useState, useEffect } from 'react';
import { Crown, Check, Clock, Video, Zap, Star, Globe, CreditCard } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PremiumPlans = ({ userEmail, onClose, onSuccess }) => {
  const [plans, setPlans] = useState({});
  const [paymentProviders, setPaymentProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingPayment, setProcessingPayment] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('premium_monthly');
  const [selectedProvider, setSelectedProvider] = useState('');

  useEffect(() => {
    loadPremiumPlans();
    loadPaymentProviders();
  }, []);

  const loadPremiumPlans = async () => {
    try {
      const response = await axios.get(`${API}/premium-plans`);
      setPlans(response.data.plans);
    } catch (error) {
      console.error('Error loading premium plans:', error);
    }
  };

  const loadPaymentProviders = async () => {
    try {
      // Try to detect user region (simplified approach)
      const userRegion = Intl.DateTimeFormat().resolvedOptions().timeZone.split('/')[0];
      const regionMap = {
        'Asia': 'IN',
        'America': 'US',
        'Europe': 'GB'
      };
      
      const response = await axios.get(`${API}/payment-providers?region=${regionMap[userRegion] || 'US'}`);
      setPaymentProviders(response.data.available_providers);
      setSelectedProvider(response.data.recommended);
    } catch (error) {
      console.error('Error loading payment providers:', error);
      // Fallback to default providers
      setPaymentProviders([
        { provider: 'stripe', name: 'Credit Card (Stripe)', description: 'Pay with Visa, Mastercard, American Express' },
        { provider: 'paypal', name: 'PayPal', description: 'Pay with PayPal account or credit card' }
      ]);
      setSelectedProvider('stripe');
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async (planType) => {
    if (!userEmail) {
      alert('Please enter your email first to upgrade to premium');
      return;
    }

    if (!selectedProvider) {
      alert('Please select a payment method');
      return;
    }

    setProcessingPayment(true);
    setSelectedPlan(planType);

    try {
      const originUrl = window.location.origin;
      
      const response = await axios.post(`${API}/create-checkout`, {
        plan_type: planType,
        user_email: userEmail,
        origin_url: originUrl,
        payment_provider: selectedProvider
      });

      // Handle different payment providers
      if (response.data.checkout_url) {
        // For Stripe/PayPal - redirect to checkout
        window.location.href = response.data.checkout_url;
      } else if (response.data.provider === 'momopay') {
        // For MomoPay - initialize MomoPay checkout
        handleMomoPayCheckout(response.data.order_details, planType);
      } else {
        throw new Error('Unknown payment provider response');
      }

    } catch (error) {
      console.error('Payment error:', error);
      alert(error.response?.data?.detail || 'Failed to create checkout session');
      setProcessingPayment(false);
    }
  };

  const handleMomoPayCheckout = (orderDetails, planType) => {
    // This would be implemented if MomoPay specific handling is needed
    // For now, fallback to other providers
    alert('MomoPay checkout not fully implemented yet. Please use Credit Card or PayPal.');
    setProcessingPayment(false);
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="bg-gray-800 rounded-2xl p-8">
          <div className="animate-pulse">Loading premium plans...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800/95 backdrop-blur-sm rounded-2xl p-8 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold text-white flex items-center gap-3">
              <Crown className="w-8 h-8 text-yellow-400" />
              Upgrade to Premium
            </h2>
            <p className="text-gray-300 mt-2">Unlock longer videos and unlimited processing</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl"
            data-testid="close-premium-modal"
          >
            ×
          </button>
        </div>

        {/* Free vs Premium Comparison */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Free Plan */}
          <div className="bg-gray-700/50 rounded-xl p-6 border-2 border-gray-600">
            <div className="text-center mb-4">
              <h3 className="text-xl font-bold text-white">Free Plan</h3>
              <div className="text-2xl font-bold text-gray-400 mt-2">$0/month</div>
            </div>
            <ul className="space-y-3">
              <li className="flex items-center gap-3 text-gray-300">
                <Check className="w-5 h-5 text-green-400" />
                Up to 5 minutes videos
              </li>
              <li className="flex items-center gap-3 text-gray-300">
                <Check className="w-5 h-5 text-green-400" />
                AI analysis & highlights
              </li>
              <li className="flex items-center gap-3 text-gray-300">
                <Check className="w-5 h-5 text-green-400" />
                Basic video segments
              </li>
            </ul>
          </div>

          {/* Premium Monthly */}
          <div className={`rounded-xl p-6 border-2 ${
            selectedPlan === 'premium_monthly' 
              ? 'border-purple-500 bg-purple-600/20' 
              : 'border-purple-400 bg-gray-700/50'
          } relative`}>
            <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
              <span className="bg-purple-500 text-white px-4 py-1 rounded-full text-sm font-semibold">
                Popular
              </span>
            </div>
            <div className="text-center mb-4">
              <h3 className="text-xl font-bold text-white">Premium Monthly</h3>
              <div className="text-3xl font-bold text-purple-400 mt-2">
                ${plans.premium_monthly?.price}/month
              </div>
            </div>
            <ul className="space-y-3 mb-6">
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Up to 30 minutes videos
              </li>
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Unlimited processing
              </li>
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Advanced AI voice-overs
              </li>
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Priority processing
              </li>
            </ul>
            <button
              onClick={() => handleUpgrade('premium_monthly')}
              disabled={processingPayment}
              className="w-full bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50"
              data-testid="upgrade-monthly-btn"
            >
              {processingPayment && selectedPlan === 'premium_monthly' ? 'Processing...' : 'Upgrade Now'}
            </button>
          </div>

          {/* Premium Yearly */}
          <div className={`rounded-xl p-6 border-2 ${
            selectedPlan === 'premium_yearly' 
              ? 'border-green-500 bg-green-600/20' 
              : 'border-green-400 bg-gray-700/50'
          } relative`}>
            <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
              <span className="bg-green-500 text-white px-4 py-1 rounded-full text-sm font-semibold">
                Best Value
              </span>
            </div>
            <div className="text-center mb-4">
              <h3 className="text-xl font-bold text-white">Premium Yearly</h3>
              <div className="text-3xl font-bold text-green-400 mt-2">
                ${plans.premium_yearly?.price}/year
              </div>
              <div className="text-sm text-green-300 mt-1">Save 2 months!</div>
            </div>
            <ul className="space-y-3 mb-6">
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Up to 30 minutes videos
              </li>
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Unlimited processing
              </li>
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Advanced AI voice-overs
              </li>
              <li className="flex items-center gap-3 text-white">
                <Check className="w-5 h-5 text-green-400" />
                Priority processing
              </li>
              <li className="flex items-center gap-3 text-white">
                <Star className="w-5 h-5 text-yellow-400" />
                2 months free
              </li>
            </ul>
            <button
              onClick={() => handleUpgrade('premium_yearly')}
              disabled={processingPayment}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-50"
              data-testid="upgrade-yearly-btn"
            >
              {processingPayment && selectedPlan === 'premium_yearly' ? 'Processing...' : 'Upgrade Now'}
            </button>
          </div>
        </div>

        {/* Payment Method Selection */}
        <div className="bg-gray-700/30 rounded-xl p-6 mb-6">
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <Globe className="w-6 h-6 text-blue-400" />
            Choose Payment Method
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {paymentProviders.map((provider) => (
              <div
                key={provider.provider}
                className={`p-4 rounded-lg cursor-pointer transition-all duration-200 border-2 ${
                  selectedProvider === provider.provider
                    ? 'border-purple-500 bg-purple-600/20'
                    : 'border-gray-600 bg-gray-800/50 hover:border-gray-500'
                }`}
                onClick={() => setSelectedProvider(provider.provider)}
                data-testid={`payment-provider-${provider.provider}`}
              >
                <div className="flex items-center gap-3 mb-2">
                  <CreditCard className="w-5 h-5 text-purple-400" />
                  <h4 className="font-semibold text-white">{provider.name}</h4>
                </div>
                <p className="text-sm text-gray-300">{provider.description}</p>
                {provider.supported_regions && (
                  <p className="text-xs text-gray-400 mt-1">
                    Regions: {Array.isArray(provider.supported_regions) ? provider.supported_regions.join(', ') : provider.supported_regions}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Features Comparison */}
        <div className="bg-gray-700/30 rounded-xl p-6">
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <Zap className="w-6 h-6 text-yellow-400" />
            Premium Features
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center gap-3">
              <Video className="w-5 h-5 text-purple-400" />
              <span className="text-gray-300">Upload videos up to 30 minutes</span>
            </div>
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-blue-400" />
              <span className="text-gray-300">Priority processing queue</span>
            </div>
            <div className="flex items-center gap-3">
              <Check className="w-5 h-5 text-green-400" />
              <span className="text-gray-300">Unlimited video processing</span>
            </div>
            <div className="flex items-center gap-3">
              <Crown className="w-5 h-5 text-yellow-400" />
              <span className="text-gray-300">Premium AI voice-over quality</span>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center text-gray-400 text-sm">
          <p>Secure payment processing • Global payment support • Cancel anytime • Revenue goes directly to your account</p>
          <p className="mt-2 flex items-center justify-center gap-2 text-xs">
            <Globe className="w-4 h-4" />
            Available worldwide with multiple payment options for your region
          </p>
        </div>
      </div>
    </div>
  );
};

export default PremiumPlans;