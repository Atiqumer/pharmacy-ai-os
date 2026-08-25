'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getApiErrorMessage } from '@/lib/apiError';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get('token');
    if (token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResetToken(token);
      setStep(2);
    }
  }, []);

  const handleRequestReset = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/password-reset-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(getApiErrorMessage(data, 'Failed to send reset request'));
      if (data.reset_token) {
        setResetToken(data.reset_token);
        setStep(2);
      } else {
        setStep(4);
      }
      setMessage(data.message);
    } catch (err) {
      setError('Failed to send reset request');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/password-reset-confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: resetToken, new_password: newPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(getApiErrorMessage(data, 'Reset failed'));
      setMessage('Password reset successful! You can now sign in.');
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
            RxOS
          </h1>
          <p className="text-slate-400 mt-2">Reset your password</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-md text-red-400 text-sm">
              {error}
            </div>
          )}
          {message && (
            <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-md text-emerald-400 text-sm">
              {message}
            </div>
          )}

          {step === 1 && (
            <form onSubmit={handleRequestReset} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-md py-2 px-4 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  placeholder="you@pharmacy.com"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white font-medium rounded-md transition-colors"
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </form>
          )}

          {step === 2 && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Reset Token</label>
                <input
                  type="text"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-md py-2 px-4 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  placeholder="Paste your reset token"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full bg-slate-950 border border-slate-800 rounded-md py-2 px-4 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  placeholder="Min 8 characters"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white font-medium rounded-md transition-colors"
              >
                {loading ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>
          )}

          {step === 3 && (
            <div className="text-center">
              <Link href="/login" className="text-cyan-400 hover:text-cyan-300">
                Go to Sign In
              </Link>
            </div>
          )}

          {step === 4 && (
            <p className="text-center text-sm text-slate-400">
              Check your email for a secure reset link. You can close this page.
            </p>
          )}

          <div className="mt-4 text-center">
            <Link href="/login" className="text-sm text-slate-400 hover:text-slate-300">
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
