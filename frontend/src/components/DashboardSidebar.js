'use client';

import { useState } from 'react';
import Link from 'next/link';
import AppIcon from './AppIcon';

const navItems = [
  { label: 'Dashboard', href: '/', icon: 'dashboard' },
  { label: 'Sales', href: '/sales', icon: 'sales' },
  { label: 'Purchasing', href: '/purchasing', icon: 'purchasing' },
];

export default function DashboardSidebar({ user, isAdmin, onLogout, children }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const navigation = (
    <>
      <nav className="space-y-1.5 px-3" aria-label="Primary navigation">
        {navItems.map((item, index) => (
          <Link key={item.href} href={item.href} className={`flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm transition ${index === 0 ? 'bg-teal-600 font-semibold text-white shadow-sm' : 'font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`} onClick={() => setMobileOpen(false)}>
            <AppIcon name={item.icon} className="h-[19px] w-[19px]" />
            {item.label}
          </Link>
        ))}
        {isAdmin && (
          <Link href="/admin" className="flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900" onClick={() => setMobileOpen(false)}>
            <AppIcon name="users" className="h-[19px] w-[19px]" />
            Team & access
          </Link>
        )}
      </nav>
      <div className="mt-auto border-t border-slate-200 p-3">
        <div className="mb-3 flex items-center gap-3 rounded-xl bg-slate-50 p-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-teal-100 text-sm font-bold text-teal-700">
            {(user.full_name || user.email || 'U').charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-800">{user.full_name || 'Pharmacy admin'}</p>
            <p className="truncate text-xs capitalize text-slate-500">{user.role}</p>
          </div>
        </div>
        <button onClick={onLogout} className="flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-500 transition hover:bg-rose-50 hover:text-rose-600">
          <AppIcon name="logout" className="h-[19px] w-[19px]" />
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#f5f7fa] text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-slate-200 bg-white lg:flex">
        <Brand />
        <div className="mt-5 flex min-h-0 flex-1 flex-col">{navigation}</div>
      </aside>

      {mobileOpen && <button aria-label="Close navigation" className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-white shadow-2xl transition-transform duration-200 lg:hidden ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between border-b border-slate-200 pr-4">
          <Brand />
          <button aria-label="Close navigation" onClick={() => setMobileOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><AppIcon name="close" /></button>
        </div>
        <div className="mt-5 flex min-h-0 flex-1 flex-col">{navigation}</div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200/90 bg-white/95 px-4 backdrop-blur md:px-8 lg:px-10">
          <div className="flex items-center gap-3">
            <button aria-label="Open navigation" onClick={() => setMobileOpen(true)} className="rounded-lg border border-slate-200 p-2 text-slate-600 lg:hidden"><AppIcon name="menu" /></button>
            <div>
              <p className="text-sm font-semibold text-slate-800">Pharmacy workspace</p>
              <p className="hidden text-xs text-slate-500 sm:block">Inventory, sales and purchasing in one place</p>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 py-1.5 pl-1.5 pr-3">
            <div className="grid h-7 w-7 place-items-center rounded-full bg-teal-600 text-xs font-bold text-white">{(user.full_name || user.email || 'U').charAt(0).toUpperCase()}</div>
            <span className="hidden max-w-40 truncate text-xs font-semibold text-slate-700 sm:block">{user.full_name || user.email}</span>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex h-16 items-center gap-3 px-5">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-teal-600 text-white shadow-sm shadow-teal-200">
        <span className="text-xl font-bold leading-none">+</span>
        <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-amber-400" />
      </div>
      <div><p className="text-lg font-extrabold tracking-tight text-slate-900">RxOS</p><p className="-mt-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-600">Pharmacy AI</p></div>
    </div>
  );
}
