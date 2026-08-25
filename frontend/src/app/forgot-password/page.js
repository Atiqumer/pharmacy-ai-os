'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getApiErrorMessage } from '@/lib/apiError';
import AuthLayout from '@/components/AuthLayout';

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
    <AuthLayout title="Reset password" description="Request a secure reset link for your pharmacy account.">
          {error && (
            <div role="alert" className="mb-4 border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          )}
          {message && (
            <div className="mb-4 border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
              {message}
            </div>
          )}

          {step === 1 && (
            <form onSubmit={handleRequestReset} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Email address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="auth-input"
                  autoComplete="email"
                  placeholder="you@pharmacy.com"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-md bg-[#18324b] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10263a] disabled:opacity-50"
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </form>
          )}

          {step === 2 && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Reset token</label>
                <input
                  type="text"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  required
                  className="auth-input"
                  placeholder="Paste your reset token"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">New password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  className="auth-input"
                  autoComplete="new-password"
                  placeholder="Min 8 characters"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-md bg-[#18324b] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10263a] disabled:opacity-50"
              >
                {loading ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>
          )}

          {step === 3 && (
            <div className="text-center">
              <Link href="/login" className="font-medium text-[#18324b] hover:underline">
                Go to Sign In
              </Link>
            </div>
          )}

          {step === 4 && (
            <p className="text-center text-sm text-slate-500">
              Check your email for a secure reset link. You can close this page.
            </p>
          )}

          <div className="mt-6 border-t border-slate-200 pt-5 text-center">
            <Link href="/login" className="text-sm font-medium text-[#18324b] hover:underline">
              Back to Sign In
            </Link>
          </div>
    </AuthLayout>
  );
}
