'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import AppIcon from './AppIcon';
import NotificationCenter from './NotificationCenter';
import PharmacyOnboarding from './PharmacyOnboarding';

const navItems = [
  { label: 'Overview', href: '/', icon: 'dashboard' },
  { label: 'Sales', href: '/sales', icon: 'sales' },
  { label: 'Purchasing', href: '/purchasing', icon: 'purchasing' },
];

const pageDetails = {
  '/': { section: 'Workspace', title: 'Overview' },
  '/sales': { section: 'Operations', title: 'Sales' },
  '/purchasing': { section: 'Operations', title: 'Purchasing' },
  '/admin': { section: 'Administration', title: 'Team & access' },
  '/settings': { section: 'Workspace', title: 'Pharmacy settings' },
};

export default function DashboardSidebar({ user, isAdmin, onLogout, authFetch, children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const currentPage = pageDetails[pathname] || pageDetails['/'];
  const initials = getInitials(user.full_name || user.email || 'User');

  useEffect(() => {
    if (window.localStorage.getItem('rxos.sidebar.collapsed') === 'true') {
      // Restore a display preference after hydration; no account data is stored here.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCollapsed(true);
    }
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((value) => {
      const nextValue = !value;
      window.localStorage.setItem('rxos.sidebar.collapsed', String(nextValue));
      return nextValue;
    });
  };

  return (
    <div className="app-shell min-h-screen text-slate-900">
      <aside className={`saas-sidebar fixed inset-y-0 left-0 z-40 hidden flex-col border-r border-white/70 transition-[width] duration-200 ease-out lg:flex ${collapsed ? 'w-[76px]' : 'w-[248px]'}`}>
        <Brand collapsed={collapsed} />
        <SidebarNavigation pathname={pathname} isAdmin={isAdmin} collapsed={collapsed} />

        <div className="mt-auto border-t border-slate-200 p-3">
          <div className={`flex items-center rounded-lg ${collapsed ? 'justify-center py-2' : 'gap-3 px-2 py-2.5'}`}>
            <Avatar initials={initials} />
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-800">{user.full_name || 'Pharmacy admin'}</p>
                <p className="truncate text-xs capitalize text-slate-500">{user.role || 'Team member'}</p>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onLogout}
            title={collapsed ? 'Sign out' : undefined}
            className={`group relative mt-1 flex w-full items-center rounded-lg py-2.5 text-sm font-medium text-slate-500 transition hover:bg-rose-50 hover:text-rose-700 ${collapsed ? 'justify-center px-2' : 'gap-3 px-3'}`}
          >
            <AppIcon name="logout" className="h-[18px] w-[18px] shrink-0" />
            {!collapsed && <span>Sign out</span>}
            {collapsed && <CollapsedTooltip>Sign out</CollapsedTooltip>}
          </button>
        </div>

        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="absolute -right-3 top-[76px] grid h-7 w-7 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-slate-300 hover:text-[#18324b]"
        >
          <AppIcon name={collapsed ? 'chevronRight' : 'chevronLeft'} className="h-4 w-4" />
        </button>
      </aside>

      {mobileOpen && (
        <button type="button" aria-label="Close navigation" className="fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-[2px] lg:hidden" onClick={() => setMobileOpen(false)} />
      )}
      <aside className={`glass-drawer fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col shadow-2xl transition-transform duration-200 lg:hidden ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex items-center justify-between border-b border-slate-200 pr-3">
          <Brand />
          <button type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><AppIcon name="close" /></button>
        </div>
        <SidebarNavigation pathname={pathname} isAdmin={isAdmin} onNavigate={() => setMobileOpen(false)} />
        <div className="mt-auto border-t border-slate-200 p-3">
          <div className="flex items-center gap-3 px-2 py-2.5">
            <Avatar initials={initials} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-800">{user.full_name || 'Pharmacy admin'}</p>
              <p className="truncate text-xs capitalize text-slate-500">{user.role || 'Team member'}</p>
            </div>
          </div>
          <button type="button" onClick={onLogout} className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-500 hover:bg-rose-50 hover:text-rose-700"><AppIcon name="logout" className="h-[18px] w-[18px]" /> Sign out</button>
        </div>
      </aside>

      <div className={`min-w-0 transition-[padding] duration-200 ease-out ${collapsed ? 'lg:pl-[76px]' : 'lg:pl-[248px]'}`}>
        <header className="saas-topbar sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/70 px-4 md:px-7">
          <div className="flex min-w-0 items-center gap-3">
            <button type="button" aria-label="Open navigation" onClick={() => setMobileOpen(true)} className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 lg:hidden"><AppIcon name="menu" className="h-[18px] w-[18px]" /></button>
            <div className="min-w-0">
              <p className="hidden text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400 sm:block">{currentPage.section}</p>
              <p className="truncate text-sm font-semibold text-slate-900 sm:mt-0.5">{currentPage.title}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600 sm:flex"><span className="h-2 w-2 rounded-full bg-emerald-500 ring-4 ring-emerald-100" /> System online</div>
            <NotificationCenter authFetch={authFetch} />
            <div className="h-7 w-px bg-slate-200" />
            <div className="flex items-center gap-2.5">
              <Avatar initials={initials} small />
              <div className="hidden min-w-0 sm:block"><p className="max-w-36 truncate text-xs font-semibold text-slate-800">{user.full_name || user.email}</p><p className="text-[10px] capitalize text-slate-500">{user.role || 'Team member'}</p></div>
            </div>
          </div>
        </header>
        {children}
      </div>
      <PharmacyOnboarding authFetch={authFetch} />
    </div>
  );
}

function SidebarNavigation({ pathname, isAdmin, collapsed = false, onNavigate }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col py-5">
      {!collapsed && <p className="mb-2 px-5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">Workspace</p>}
      <nav className={`space-y-1 ${collapsed ? 'px-2.5' : 'px-3'}`} aria-label="Primary navigation">
        {navItems.map((item) => <NavItem key={item.href} item={item} active={item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)} collapsed={collapsed} onNavigate={onNavigate} />)}
      </nav>
      <>
        <div className={`my-4 border-t border-slate-200 ${collapsed ? 'mx-3' : 'mx-4'}`} />
        {!collapsed && <p className="mb-2 px-5 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">Manage</p>}
        <nav className={`space-y-1 ${collapsed ? 'px-2.5' : 'px-3'}`} aria-label="Workspace settings">
          <NavItem item={{ label: 'Pharmacy settings', href: '/settings', icon: 'settings' }} active={pathname.startsWith('/settings')} collapsed={collapsed} onNavigate={onNavigate} />
          {isAdmin && (
            <NavItem item={{ label: 'Team & access', href: '/admin', icon: 'users' }} active={pathname.startsWith('/admin')} collapsed={collapsed} onNavigate={onNavigate} />
          )}
        </nav>
      </>
    </div>
  );
}

function NavItem({ item, active, collapsed, onNavigate }) {
  return (
    <Link href={item.href} title={collapsed ? item.label : undefined} aria-current={active ? 'page' : undefined} className={`group relative flex items-center rounded-lg py-2.5 text-sm transition ${collapsed ? 'justify-center px-2' : 'gap-3 px-3'} ${active ? 'bg-[#eaf0f5] font-semibold text-[#18324b]' : 'font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-950'}`} onClick={onNavigate}>
      {active && <span className={`absolute bg-[#18324b] ${collapsed ? '-left-2.5 h-6 w-[3px] rounded-r-full' : 'left-0 h-5 w-[3px] rounded-r-full'}`} />}
      <AppIcon name={item.icon} className="h-[19px] w-[19px] shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {collapsed && <CollapsedTooltip>{item.label}</CollapsedTooltip>}
    </Link>
  );
}

function CollapsedTooltip({ children }) {
  return <span className="pointer-events-none absolute left-[calc(100%+10px)] z-50 whitespace-nowrap rounded-md bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-lg transition group-hover:opacity-100">{children}</span>;
}

function Avatar({ initials, small = false }) {
  return <div className={`grid shrink-0 place-items-center rounded-lg bg-[#e7edf3] font-bold text-[#18324b] ${small ? 'h-8 w-8 text-[11px]' : 'h-9 w-9 text-xs'}`}>{initials}</div>;
}

function Brand({ collapsed = false }) {
  return (
    <Link href="/" aria-label="RxOS dashboard" className={`flex h-16 shrink-0 items-center border-b border-slate-100 ${collapsed ? 'justify-center px-3' : 'gap-3 px-5'}`}>
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#18324b] text-white shadow-sm"><span className="text-xl font-semibold leading-none">+</span></div>
      {!collapsed && <div className="min-w-0"><p className="text-[17px] font-extrabold tracking-tight text-slate-950">RxOS</p><p className="mt-0.5 text-[10px] font-semibold tracking-wide text-slate-500">Pharmacy operations</p></div>}
    </Link>
  );
}

function getInitials(value) {
  return value.split(/\s+|@/).filter(Boolean).slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join('');
}
