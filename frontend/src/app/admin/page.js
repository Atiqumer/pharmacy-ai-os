'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import DashboardSidebar from '@/components/DashboardSidebar';
import { fetchWithRetry } from '@/lib/fetchWithRetry';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function AdminPage() {
  const { user, loading, authFetch, isAdmin, logout } = useAuth();
  const router = useRouter();

  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [actionLoading, setActionLoading] = useState('');

  useEffect(() => {
    if (!loading && (!user || !isAdmin)) {
      router.push('/');
    }
  }, [user, loading, isAdmin, router]);

  const fetchUsers = async (p = 1) => {
    try {
      const res = await fetchWithRetry(authFetch, `${API_URL}/admin/users?page=${p}&limit=10`);
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users);
        setTotal(data.total);
        setPage(p);
      }
    } catch (err) {
      console.error('Failed to fetch users');
    }
  };

  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;

    async function loadUsers() {
      try {
        const res = await fetchWithRetry(authFetch, `${API_URL}/admin/users?page=1&limit=10`);
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (!cancelled) {
          setUsers(data.users);
          setTotal(data.total);
          setPage(1);
        }
      } catch {
        if (!cancelled) console.error('Failed to fetch users');
      }
    }

    loadUsers();
    return () => { cancelled = true; };
  }, [isAdmin, authFetch]);

  const updateRole = async (userId, newRole) => {
    setActionLoading(userId);
    try {
      await authFetch(`${API_URL}/admin/users/role`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, role: newRole }),
      });
      fetchUsers(page);
    } finally {
      setActionLoading('');
    }
  };

  const toggleActive = async (userId, isActive) => {
    setActionLoading(userId);
    try {
      await authFetch(`${API_URL}/admin/users/active`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, is_active: !isActive }),
      });
      fetchUsers(page);
    } finally {
      setActionLoading('');
    }
  };

  const archiveUser = async (userId) => {
    if (!confirm('Archive this user? Their access will be disabled and business records will be preserved.')) return;
    setActionLoading(userId);
    try {
      await authFetch(`${API_URL}/admin/users/${userId}`, { method: 'DELETE' });
      fetchUsers(page);
    } finally {
      setActionLoading('');
    }
  };

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <p className="text-sm text-slate-500">Loading…</p>
      </main>
    );
  }

  if (!isAdmin) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <p className="text-sm text-rose-700">Access denied. Admin only.</p>
      </main>
    );
  }

  return (
    <DashboardSidebar user={user} isAdmin={isAdmin} onLogout={logout} authFetch={authFetch}>
    <main className="app-content min-h-screen px-4 py-6 md:px-7 md:py-7">
      <div className="mx-auto max-w-[1200px] space-y-7">
        <header className="border-b border-slate-200 pb-6">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Team & access</h1>
          <p className="mt-1.5 text-sm text-slate-500">Manage operator roles and account status.</p>
        </header>

        <section className="glass-panel rounded-xl border border-white/80 p-4 sm:p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-slate-950">Users ({total})</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-slate-200 transition-colors hover:bg-slate-50/80">
                    <td className="px-4 py-3">{u.email}</td>
                    <td className="px-4 py-3">{u.full_name}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => updateRole(u.id, e.target.value)}
                        disabled={actionLoading === u.id || u.id === user.id}
                        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 disabled:bg-slate-100 disabled:text-slate-500"
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${u.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 space-x-2">
                      <button
                        onClick={() => toggleActive(u.id, u.is_active)}
                        disabled={actionLoading === u.id || u.id === user.id}
                        className="ui-secondary min-h-8 px-2.5 py-1 text-xs"
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        onClick={() => archiveUser(u.id)}
                        disabled={actionLoading === u.id || u.id === user.id}
                        className="ui-danger min-h-8 px-2.5 py-1 text-xs"
                      >
                        Archive
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > 10 && (
            <div className="flex justify-center gap-2 mt-4">
              <button
                onClick={() => fetchUsers(page - 1)}
                disabled={page === 1}
                className="ui-secondary min-h-8 px-3 py-1"
              >
                Prev
              </button>
              <span className="px-3 py-1 text-sm text-slate-400">Page {page}</span>
              <button
                onClick={() => fetchUsers(page + 1)}
                disabled={page * 10 >= total}
                className="ui-secondary min-h-8 px-3 py-1"
              >
                Next
              </button>
            </div>
          )}
        </section>
      </div>
    </main>
    </DashboardSidebar>
  );
}
