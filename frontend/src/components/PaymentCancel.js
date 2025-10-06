import React from 'react';
import { XCircle, ArrowLeft, Crown } from 'lucide-react';

const PaymentCancel = () => {
  const goToHome = () => {
    window.location.href = '/';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
      <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-8 max-w-md w-full mx-4 text-center">
        <div className="w-16 h-16 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <XCircle className="w-10 h-10 text-orange-400" />
        </div>
        
        <h2 className="text-2xl font-bold text-white mb-4">Payment Cancelled</h2>
        
        <p className="text-gray-300 mb-6">
          No worries! Your payment was cancelled and you haven't been charged anything.
        </p>

        <div className="bg-gray-700/50 rounded-xl p-6 mb-6">
          <h3 className="text-lg font-semibold text-white mb-3 flex items-center justify-center gap-2">
            <Crown className="w-5 h-5 text-yellow-400" />
            Premium Benefits Waiting
          </h3>
          <ul className="text-left space-y-2 text-gray-300 text-sm">
            <li>• Upload videos up to 30 minutes</li>
            <li>• Unlimited video processing</li>
            <li>• Priority processing queue</li>
            <li>• Advanced AI voice-overs</li>
          </ul>
        </div>

        <div className="space-y-3">
          <button
            onClick={() => window.location.href = '/?upgrade=true'}
            className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold py-3 px-6 rounded-lg transition-all duration-200"
            data-testid="try-again-btn"
          >
            Try Premium Again
          </button>
          
          <button
            onClick={goToHome}
            className="w-full bg-gray-600 hover:bg-gray-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors flex items-center justify-center gap-2"
            data-testid="return-home-btn"
          >
            <ArrowLeft className="w-5 h-5" />
            Continue with Free Plan
          </button>
        </div>
      </div>
    </div>
  );
};

export default PaymentCancel;