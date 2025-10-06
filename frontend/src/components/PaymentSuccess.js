import React, { useState, useEffect } from 'react';
import { CheckCircle, Crown, ArrowRight, Home } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PaymentSuccess = () => {
  const [paymentStatus, setPaymentStatus] = useState('checking');
  const [paymentDetails, setPaymentDetails] = useState(null);
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    if (sessionId) {
      pollPaymentStatus(sessionId);
    } else {
      setPaymentStatus('error');
    }
  }, []);

  const pollPaymentStatus = async (sessionId, currentAttempts = 0) => {
    const maxAttempts = 10;
    const pollInterval = 2000; // 2 seconds

    if (currentAttempts >= maxAttempts) {
      setPaymentStatus('timeout');
      return;
    }

    try {
      const response = await axios.get(`${API}/payment-status/${sessionId}`);
      const data = response.data;
      
      if (data.payment_status === 'paid') {
        setPaymentStatus('success');
        setPaymentDetails(data);
        return;
      } else if (data.status === 'expired') {
        setPaymentStatus('expired');
        return;
      }

      // If payment is still pending, continue polling
      setAttempts(currentAttempts + 1);
      setTimeout(() => pollPaymentStatus(sessionId, currentAttempts + 1), pollInterval);
    } catch (error) {
      console.error('Error checking payment status:', error);
      setPaymentStatus('error');
    }
  };

  const goToHome = () => {
    window.location.href = '/';
  };

  if (paymentStatus === 'checking') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-8 max-w-md w-full mx-4 text-center">
          <div className="animate-spin w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full mx-auto mb-6"></div>
          <h2 className="text-2xl font-bold text-white mb-2">Processing Payment...</h2>
          <p className="text-gray-300">Please wait while we confirm your payment</p>
          <p className="text-sm text-gray-400 mt-2">Attempt {attempts + 1}/10</p>
        </div>
      </div>
    );
  }

  if (paymentStatus === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-8 max-w-lg w-full mx-4 text-center">
          <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-12 h-12 text-green-400" />
          </div>
          
          <h1 className="text-3xl font-bold text-white mb-4 flex items-center justify-center gap-3">
            <Crown className="w-8 h-8 text-yellow-400" />
            Welcome to Premium!
          </h1>
          
          <p className="text-xl text-gray-300 mb-6">
            Your payment was successful and your premium plan is now active!
          </p>

          {paymentDetails && (
            <div className="bg-gray-700/50 rounded-xl p-6 mb-6 text-left">
              <h3 className="text-lg font-semibold text-white mb-4">Payment Details</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-300">Plan:</span>
                  <span className="text-white font-medium">
                    {paymentDetails.plan_type === 'premium_monthly' ? 'Premium Monthly' : 'Premium Yearly'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Amount:</span>
                  <span className="text-white font-medium">${paymentDetails.amount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Status:</span>
                  <span className="text-green-400 font-medium">Paid ✓</span>
                </div>
              </div>
            </div>
          )}

          <div className="bg-purple-600/20 rounded-xl p-6 mb-6">
            <h3 className="text-lg font-semibold text-white mb-3">Premium Benefits Unlocked</h3>
            <ul className="text-left space-y-2 text-gray-300">
              <li className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                Upload videos up to 30 minutes
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                Unlimited video processing
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                Priority processing queue
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                Advanced AI voice-overs
              </li>
            </ul>
          </div>

          <button
            onClick={goToHome}
            className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
            data-testid="return-home-btn"
          >
            <Home className="w-5 h-5" />
            Start Using Premium Features
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    );
  }

  // Error states
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
      <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-8 max-w-md w-full mx-4 text-center">
        <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <span className="text-red-400 text-2xl">⚠️</span>
        </div>
        
        <h2 className="text-2xl font-bold text-white mb-4">
          {paymentStatus === 'timeout' ? 'Payment Check Timeout' : 
           paymentStatus === 'expired' ? 'Payment Session Expired' : 'Payment Error'}
        </h2>
        
        <p className="text-gray-300 mb-6">
          {paymentStatus === 'timeout' 
            ? 'We couldn\'t verify your payment in time. Please check your email for confirmation or contact support.'
            : paymentStatus === 'expired'
            ? 'Your payment session has expired. Please try again.'
            : 'There was an error processing your payment. Please try again or contact support.'}
        </p>

        <button
          onClick={goToHome}
          className="w-full bg-gray-600 hover:bg-gray-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Home className="w-5 h-5" />
          Return to Home
        </button>
      </div>
    </div>
  );
};

export default PaymentSuccess;