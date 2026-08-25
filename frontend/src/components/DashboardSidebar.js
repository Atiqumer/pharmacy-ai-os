'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import AppIcon from './AppIcon';

const navItems = [
  { label: 'Dashboard', href: '/', icon: 'dashboard' },
  { label: 'Sales', href: '/sales', icon: 'sales' },
  { label: 'Purchasing', href: '/purchasing', icon: 'purchasing' },
];

export default function DashboardSidebar({ user, isAdmin, onLogout, children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  const navigation = (
    <>
      <nav className="space-y-1.5 px-3" aria-label="Primary navigation">
        {navItems.map((item) => {
          const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
          return <Link key={item.href} href={item.href} className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition ${active ? 'bg-[#18324b] font-semibold text-white' : 'font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`} onClick={() => setMobileOpen(false)}>
            <AppIcon name={item.icon} className="h-[19px] w-[19px]" />
            {item.label}
          </Link>;
        })}
        {isAdmin && (
          <Link href="/admin" className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition ${pathname.startsWith('/admin') ? 'bg-[#18324b] text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`} onClick={() => setMobileOpen(false)}>
            <AppIcon name="users" className="h-[19px] w-[19px]" />
            Team & access
          </Link>
        )}
      </nav>
      <div className="mt-auto border-t border-slate-200 p-3">
        <div className="mb-2 flex items-center gap-3 border-t border-slate-200 px-1 pt-4">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-200 text-xs font-bold text-slate-700">
            {(user.full_name || user.email || 'U').charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-800">{user.full_name || 'Pharmacy admin'}</p>
            <p className="truncate text-xs capitalize text-slate-500">{user.role}</p>
          </div>
        </div>
        <button onClick={onLogout} className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-slate-500 transition hover:bg-rose-50 hover:text-rose-600">
          <AppIcon name="logout" className="h-[19px] w-[19px]" />
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <div className="app-shell min-h-screen bg-[#f6f7f9] text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-slate-200 bg-white lg:flex">
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

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 md:px-8 lg:px-9">
          <div className="flex items-center gap-3">
            <button aria-label="Open navigation" onClick={() => setMobileOpen(true)} className="rounded-lg border border-slate-200 p-2 text-slate-600 lg:hidden"><AppIcon name="menu" /></button>
            <div>
              <p className="text-sm font-semibold text-slate-800">Pharmacy operations</p>
            </div>
          </div>
          <div className="flex items-center gap-2 border-l border-slate-200 pl-4">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-slate-200 text-xs font-bold text-slate-700">{(user.full_name || user.email || 'U').charAt(0).toUpperCase()}</div>
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
      <div className="relative grid h-9 w-9 place-items-center rounded-md bg-[#18324b] text-white">
        <span className="text-xl font-bold leading-none">+</span>
      </div>
      <div><p className="text-lg font-extrabold tracking-tight text-slate-900">RxOS</p><p className="-mt-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Pharmacy system</p></div>
    </div>
  );
}
