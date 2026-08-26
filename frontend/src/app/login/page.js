'use client';
import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import AuthLayout from '@/components/AuthLayout';

export default function LoginPage() {
  const { login, signup } = useAuth();
  const router = useRouter();
  const [isSignup, setIsSignup] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isSignup) {
        await signup(email, password, fullName);
      } else {
        await login(email, password, remember);
      }
      router.push('/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title={isSignup ? 'Create your account' : 'Sign in'} description={isSignup ? 'Set up a pharmacy operator account.' : 'Use your pharmacy account to continue.'}>
      {error && <div role="alert" className="mb-5 border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">{error}</div>}
      <form onSubmit={handleSubmit} className="space-y-4">
            {isSignup && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Full name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="auth-input"
                  autoComplete="name"
                  placeholder="Your name"
                />
              </div>
            )}

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

            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="auth-input"
                autoComplete={isSignup ? 'new-password' : 'current-password'}
                placeholder="Min 8 characters"
              />
            </div>

            {!isSignup && <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-[#18324b]" />Keep me signed in</label>}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-md bg-[#18324b] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#10263a] disabled:opacity-50"
            >
              {loading ? 'Please wait...' : isSignup ? 'Create Account' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 border-t border-slate-200 pt-5 text-center">
            <button
              onClick={() => { setIsSignup(!isSignup); setError(''); }}
              className="text-sm font-medium text-[#18324b] hover:underline"
            >
              {isSignup ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
            </button>
          </div>
          {!isSignup && <p className="mt-5 text-center text-xs leading-5 text-slate-400">Sessions close with the browser unless you choose to stay signed in. Inactive sessions end after 30 minutes.</p>}
    </AuthLayout>
  );
}
