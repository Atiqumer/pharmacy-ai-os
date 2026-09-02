'use client';

import { useCallback, useEffect, useState } from 'react';
import AppIcon from './AppIcon';
import { getApiErrorMessage } from '@/lib/apiError';
import { fetchWithRetry } from '@/lib/fetchWithRetry';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function PharmacyOnboarding({ authFetch, onComplete }) {
  const [status, setStatus] = useState('loading');
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const loadSetup = useCallback(async () => {
    setStatus('loading');
    setError('');
    try {
      const response = await fetchWithRetry(authFetch, `${API_URL}/settings/pharmacy`);
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Pharmacy setup could not be loaded'));
      setStatus(data.setup_complete ? 'complete' : 'required');
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  }, [authFetch]);

  useEffect(() => {
    // Setup state is hydrated from the authenticated API after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadSetup();
  }, [loadSetup]);

  const saveSetup = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    const form = new FormData(event.currentTarget);
    const payload = {
      name: form.get('name'),
      phone: form.get('phone') || null,
      address: form.get('address') || null,
      expiry_alert_days: Number(form.get('expiry_alert_days')),
      low_stock_alerts: form.get('low_stock_alerts') === 'on',
      expiry_alerts: form.get('expiry_alerts') === 'on',
    };
    try {
      const response = await authFetch(`${API_URL}/settings/pharmacy`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Pharmacy setup could not be saved'));
      setStatus('complete');
      onComplete?.(data.profile);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (status === 'loading' || status === 'complete') return null;

  return (
    <div className="fixed inset-0 z-[80] grid place-items-center overflow-y-auto bg-slate-950/45 p-4 backdrop-blur-md">
      <section role="dialog" aria-modal="true" aria-labelledby="setup-title" className="glass-onboarding my-6 w-full max-w-xl overflow-hidden rounded-2xl border border-white/80">
        <div className="border-b border-slate-200/80 px-6 py-5 sm:px-8">
          <div className="flex items-center justify-between gap-5">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#18324b] text-lg font-semibold text-white">+</div>
              <div><p className="text-sm font-bold text-slate-950">Set up RxOS</p><p className="text-xs text-slate-500">Your single-pharmacy workspace</p></div>
            </div>
            {status !== 'error' && <span className="text-xs font-semibold text-slate-500">Step {step} of 2</span>}
          </div>
          {status !== 'error' && <div className="mt-4 h-1 overflow-hidden rounded-full bg-slate-200"><div className={`h-full rounded-full bg-[#18324b] transition-[width] ${step === 1 ? 'w-1/2' : 'w-full'}`} /></div>}
        </div>

        {status === 'error' ? (
          <div className="px-6 py-10 text-center sm:px-8">
            <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-rose-50 text-rose-700"><AppIcon name="alert" /></div>
            <h1 id="setup-title" className="mt-4 text-xl font-semibold text-slate-950">Setup is temporarily unavailable</h1>
            <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">{error}</p>
            <button type="button" onClick={loadSetup} className="mt-6 rounded-lg bg-[#18324b] px-4 py-2.5 text-sm font-semibold text-white">Try again</button>
          </div>
        ) : step === 1 ? (
          <div className="px-6 py-7 sm:px-8">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#315a77]">Welcome</p>
            <h1 id="setup-title" className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Prepare your pharmacy workspace</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">A short setup lets RxOS label your workspace and decide when stock and expiry alerts should appear.</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <SetupBenefit icon="alert" title="Live inventory alerts" text="See low-stock and expiry risks inside the dashboard." />
              <SetupBenefit icon="settings" title="Your alert window" text="Choose how early upcoming expiries should be flagged." />
            </div>
            <div className="mt-7 flex justify-end"><button type="button" onClick={() => setStep(2)} className="inline-flex items-center gap-2 rounded-lg bg-[#18324b] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10263a]">Continue <AppIcon name="arrow" className="h-4 w-4" /></button></div>
          </div>
        ) : (
          <form onSubmit={saveSetup} className="px-6 py-7 sm:px-8">
            <h1 id="setup-title" className="text-xl font-semibold text-slate-950">Pharmacy details</h1>
            <p className="mt-1 text-sm text-slate-500">You can change these settings later.</p>
            <div className="mt-6 space-y-4">
              <label className="block text-sm font-medium text-slate-700">Pharmacy name<span className="text-rose-600"> *</span><input required minLength="2" maxLength="255" name="name" autoFocus placeholder="e.g. City Care Pharmacy" className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white/90 px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]" /></label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block text-sm font-medium text-slate-700">Phone <span className="font-normal text-slate-400">(optional)</span><input maxLength="50" name="phone" placeholder="0300 1234567" className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white/90 px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]" /></label>
                <label className="block text-sm font-medium text-slate-700">Expiry warning<select name="expiry_alert_days" defaultValue="90" className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white/90 px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]"><option value="30">30 days before</option><option value="60">60 days before</option><option value="90">90 days before</option><option value="180">180 days before</option></select></label>
              </div>
              <label className="block text-sm font-medium text-slate-700">Address <span className="font-normal text-slate-400">(optional)</span><textarea name="address" maxLength="500" rows="2" placeholder="Pharmacy address" className="mt-1.5 w-full resize-none rounded-lg border border-slate-300 bg-white/90 px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]" /></label>
              <div className="grid gap-2 sm:grid-cols-2">
                <Toggle name="low_stock_alerts" label="Low-stock alerts" defaultChecked />
                <Toggle name="expiry_alerts" label="Expiry alerts" defaultChecked />
              </div>
            </div>
            {error && <div role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
            <div className="mt-7 flex items-center justify-between gap-3"><button type="button" onClick={() => setStep(1)} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">Back</button><button disabled={saving} className="rounded-lg bg-[#18324b] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#10263a] disabled:opacity-50">{saving ? 'Saving…' : 'Finish setup'}</button></div>
          </form>
        )}
      </section>
    </div>
  );
}

function SetupBenefit({ icon, title, text }) {
  return <div className="rounded-xl border border-slate-200/80 bg-white/55 p-4"><AppIcon name={icon} className="h-5 w-5 text-[#315a77]" /><p className="mt-3 text-sm font-semibold text-slate-900">{title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{text}</p></div>;
}

function Toggle({ name, label, defaultChecked }) {
  return <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 bg-white/60 px-3 py-3 text-sm font-medium text-slate-700"><input type="checkbox" name={name} defaultChecked={defaultChecked} className="h-4 w-4 accent-[#18324b]" />{label}</label>;
}
