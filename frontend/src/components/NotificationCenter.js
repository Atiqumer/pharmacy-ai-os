'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import AppIcon from './AppIcon';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function NotificationCenter({ authFetch, refreshKey = 0 }) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const panelRef = useRef(null);

  const loadNotifications = useCallback(async () => {
    setError('');
    try {
      const response = await authFetch(`${API_URL}/notifications`);
      const data = await response.json();
      if (!response.ok) throw new Error('Notifications could not be loaded');
      setNotifications(data.notifications || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    // Notifications are an external API feed and are hydrated after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadNotifications();
    const interval = window.setInterval(loadNotifications, 120000);
    return () => window.clearInterval(interval);
  }, [loadNotifications, refreshKey]);

  useEffect(() => {
    if (!open) return undefined;
    const closePanel = (event) => {
      if (event.key === 'Escape' || (event.type === 'mousedown' && !panelRef.current?.contains(event.target))) setOpen(false);
    };
    document.addEventListener('mousedown', closePanel);
    document.addEventListener('keydown', closePanel);
    return () => {
      document.removeEventListener('mousedown', closePanel);
      document.removeEventListener('keydown', closePanel);
    };
  }, [open]);

  const criticalCount = notifications.filter((item) => item.severity === 'critical').length;

  return (
    <div className="relative" ref={panelRef}>
      <button type="button" onClick={() => setOpen((value) => !value)} aria-label={`${notifications.length} active inventory alerts`} aria-expanded={open} className="relative grid h-9 w-9 place-items-center rounded-lg border border-slate-200/90 bg-white/65 text-slate-600 transition hover:bg-white hover:text-[#18324b]">
        <AppIcon name="bell" className="h-[18px] w-[18px]" />
        {notifications.length > 0 && <span className={`absolute -right-1.5 -top-1.5 grid h-5 min-w-5 place-items-center rounded-full px-1 text-[10px] font-bold text-white ring-2 ring-white ${criticalCount ? 'bg-rose-600' : 'bg-amber-500'}`}>{notifications.length > 99 ? '99+' : notifications.length}</span>}
      </button>

      {open && (
        <div className="glass-notification-panel absolute right-0 top-12 z-50 w-[min(390px,calc(100vw-2rem))] overflow-hidden rounded-xl border border-white/80 text-left">
          <div className="flex items-center justify-between border-b border-slate-200/80 px-4 py-3.5">
            <div><p className="text-sm font-semibold text-slate-950">Inventory alerts</p><p className="mt-0.5 text-xs text-slate-500">{notifications.length} active · updates every 2 minutes</p></div>
            <button type="button" onClick={loadNotifications} className="rounded-md px-2 py-1 text-xs font-semibold text-[#315a77] hover:bg-slate-100">Refresh</button>
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {loading && <p className="px-4 py-10 text-center text-sm text-slate-500">Checking inventory…</p>}
            {!loading && error && <div className="p-4"><p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p></div>}
            {!loading && !error && notifications.length === 0 && <div className="px-6 py-10 text-center"><div className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-emerald-50 text-emerald-700"><AppIcon name="check" /></div><p className="mt-3 text-sm font-semibold text-slate-800">No active alerts</p><p className="mt-1 text-xs text-slate-500">Stock and expiry levels look healthy.</p></div>}
            {!loading && !error && notifications.map((notification) => <NotificationItem key={notification.id} notification={notification} onNavigate={() => setOpen(false)} />)}
          </div>
          <Link href="/settings" onClick={() => setOpen(false)} className="flex items-center justify-center gap-2 border-t border-slate-200/80 px-4 py-3 text-xs font-semibold text-[#315a77] hover:bg-white/60"><AppIcon name="settings" className="h-4 w-4" /> Alert settings</Link>
        </div>
      )}
    </div>
  );
}

function NotificationItem({ notification, onNavigate }) {
  const tone = notification.severity === 'critical'
    ? 'bg-rose-100 text-rose-700'
    : notification.severity === 'warning' ? 'bg-amber-100 text-amber-700' : 'bg-sky-100 text-sky-700';
  return (
    <Link href={notification.action_url || '/'} onClick={onNavigate} className="flex gap-3 border-b border-slate-100 px-4 py-3.5 transition last:border-0 hover:bg-white/65">
      <div className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${tone}`}><AppIcon name={notification.type === 'expiry' ? 'calendar' : 'package'} className="h-4 w-4" /></div>
      <div className="min-w-0"><div className="flex items-center gap-2"><p className="text-sm font-semibold text-slate-900">{notification.title}</p><span className={`h-1.5 w-1.5 rounded-full ${notification.severity === 'critical' ? 'bg-rose-500' : notification.severity === 'warning' ? 'bg-amber-500' : 'bg-sky-500'}`} /></div><p className="mt-1 text-xs leading-5 text-slate-500">{notification.message}</p></div>
    </Link>
  );
}
