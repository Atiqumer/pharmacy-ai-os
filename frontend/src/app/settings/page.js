'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import DashboardSidebar from '@/components/DashboardSidebar';
import AppIcon from '@/components/AppIcon';
import { useAuth } from '@/contexts/AuthContext';
import { getApiErrorMessage } from '@/lib/apiError';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function PharmacySettingsPage() {
  const { user, loading: authLoading, authFetch, logout, isAdmin } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [authLoading, router, user]);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await authFetch(`${API_URL}/settings/pharmacy`);
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Pharmacy settings could not be loaded'));
      setProfile(data.profile);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    // Profile settings are hydrated from the authenticated API after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) loadProfile();
  }, [loadProfile, user]);

  const saveProfile = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
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
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Pharmacy settings could not be saved'));
      setProfile(data.profile);
      setSuccess('Pharmacy settings saved. Notifications will use the new alert preferences.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || !user) return <main className="grid min-h-screen place-items-center bg-slate-100 text-sm text-slate-500">Loading…</main>;

  return (
    <DashboardSidebar user={user} isAdmin={isAdmin} onLogout={logout} authFetch={authFetch}>
      <main className="app-content min-h-screen px-4 py-6 md:px-7 md:py-7">
        <div className="mx-auto max-w-[1100px] space-y-7">
          <header className="border-b border-slate-200 pb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Pharmacy settings</h1>
            <p className="mt-1.5 text-sm text-slate-500">Manage this workspace and choose which inventory alerts appear.</p>
          </header>

          {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
          {success && <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{success}</div>}

          {loading ? <div className="glass-panel rounded-xl border border-white/80 p-10 text-center text-sm text-slate-500">Loading pharmacy settings…</div> : profile && (
            <form onSubmit={saveProfile} className="grid gap-5 lg:grid-cols-[1fr_340px]">
              <section className="glass-panel overflow-hidden rounded-xl border border-white/80">
                <div className="border-b border-slate-200/80 px-5 py-4"><h2 className="text-sm font-semibold text-slate-900">Workspace profile</h2><p className="mt-1 text-xs text-slate-500">Basic details used to identify your pharmacy workspace.</p></div>
                <div className="space-y-5 p-5">
                  <label className="block text-sm font-medium text-slate-700">Pharmacy name<input required minLength="2" maxLength="255" name="name" defaultValue={profile.name} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]" /></label>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <label className="block text-sm font-medium text-slate-700">Phone<input maxLength="50" name="phone" defaultValue={profile.phone || ''} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]" /></label>
                    <label className="block text-sm font-medium text-slate-700">Account email<input disabled value={user.email} className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2.5 text-sm text-slate-500" /></label>
                  </div>
                  <label className="block text-sm font-medium text-slate-700">Address<textarea name="address" maxLength="500" rows="3" defaultValue={profile.address || ''} className="mt-1.5 w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]" /></label>
                </div>
              </section>

              <section className="glass-panel h-fit overflow-hidden rounded-xl border border-white/80">
                <div className="border-b border-slate-200/80 px-5 py-4"><div className="flex items-center gap-2"><AppIcon name="bell" className="h-4 w-4 text-[#315a77]" /><h2 className="text-sm font-semibold text-slate-900">Notification preferences</h2></div><p className="mt-1 text-xs text-slate-500">Alerts appear only inside RxOS.</p></div>
                <div className="space-y-4 p-5">
                  <PreferenceToggle name="low_stock_alerts" label="Low-stock alerts" description="Alert when total product stock reaches its configured minimum." defaultChecked={profile.low_stock_alerts} />
                  <PreferenceToggle name="expiry_alerts" label="Expiry alerts" description="Alert for active batches approaching their expiry date." defaultChecked={profile.expiry_alerts} />
                  <label className="block border-t border-slate-200 pt-4 text-sm font-medium text-slate-700">Expiry warning window<select name="expiry_alert_days" defaultValue={String(profile.expiry_alert_days)} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-[#18324b] focus:ring-2 focus:ring-[#dce7f0]"><option value="30">30 days</option><option value="60">60 days</option><option value="90">90 days</option><option value="180">180 days</option><option value="365">365 days</option></select></label>
                  <button disabled={saving} className="w-full rounded-lg bg-[#18324b] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10263a] disabled:opacity-50">{saving ? 'Saving…' : 'Save settings'}</button>
                </div>
              </section>
            </form>
          )}
        </div>
      </main>
    </DashboardSidebar>
  );
}

function PreferenceToggle({ name, label, description, defaultChecked }) {
  return <label className="flex cursor-pointer items-start gap-3"><input type="checkbox" name={name} defaultChecked={defaultChecked} className="mt-0.5 h-4 w-4 shrink-0 accent-[#18324b]" /><span><span className="block text-sm font-semibold text-slate-800">{label}</span><span className="mt-0.5 block text-xs leading-5 text-slate-500">{description}</span></span></label>;
}
