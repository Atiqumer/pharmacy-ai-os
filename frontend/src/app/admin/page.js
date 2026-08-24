'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function AdminPage() {
  const { user, loading, authFetch, isAdmin } = useAuth();
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
      const res = await authFetch(`${API_URL}/admin/users?page=${p}&limit=10`);
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
        const res = await authFetch(`${API_URL}/admin/users?page=1&limit=10`);
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

  const deleteUser = async (userId) => {
    if (!confirm('Are you sure you want to delete this user?')) return;
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
      <main className="min-h-screen bg-slate-950 flex items-center justify-center">
        <p className="text-slate-400">Loading...</p>
      </main>
    );
  }

  if (!isAdmin) {
    return (
      <main className="min-h-screen bg-slate-950 flex items-center justify-center">
        <p className="text-red-400">Access denied. Admin only.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-5xl mx-auto space-y-8">
        <header className="border-b border-slate-800 pb-6">
          <h1 className="text-3xl font-bold text-slate-100">Admin Panel</h1>
          <p className="text-slate-400 mt-2">Manage users and system settings</p>
        </header>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-slate-200">Users ({total})</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="text-xs uppercase bg-slate-950 text-slate-400">
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
                  <tr key={u.id} className="border-b border-slate-800 hover:bg-slate-800/50">
                    <td className="px-4 py-3">{u.email}</td>
                    <td className="px-4 py-3">{u.full_name}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => updateRole(u.id, e.target.value)}
                        disabled={actionLoading === u.id || u.id === user.id}
                        className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs"
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-1 rounded ${u.is_active ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 space-x-2">
                      <button
                        onClick={() => toggleActive(u.id, u.is_active)}
                        disabled={actionLoading === u.id || u.id === user.id}
                        className="text-xs px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded transition-colors disabled:opacity-50"
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        onClick={() => deleteUser(u.id)}
                        disabled={actionLoading === u.id || u.id === user.id}
                        className="text-xs px-2 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded transition-colors disabled:opacity-50"
                      >
                        Delete
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
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded text-sm disabled:opacity-50"
              >
                Prev
              </button>
              <span className="px-3 py-1 text-sm text-slate-400">Page {page}</span>
              <button
                onClick={() => fetchUsers(page + 1)}
                disabled={page * 10 >= total}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
