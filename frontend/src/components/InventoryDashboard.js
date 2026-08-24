'use client';

import { useCallback, useEffect, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const money = new Intl.NumberFormat('en-PK', {
  style: 'currency',
  currency: 'PKR',
  maximumFractionDigits: 0,
});

function expiryLabel(expiryDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const expiry = new Date(`${expiryDate}T00:00:00`);
  const days = Math.ceil((expiry - today) / 86400000);
  if (days < 0) return { text: 'Expired', className: 'bg-red-500/15 text-red-300' };
  if (days <= 90) return { text: `${days}d left`, className: 'bg-amber-500/15 text-amber-300' };
  return { text: 'Valid', className: 'bg-emerald-500/15 text-emerald-300' };
}

export default function InventoryDashboard({ authFetch, refreshKey = 0 }) {
  const [summary, setSummary] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [draftSearch, setDraftSearch] = useState('');
  const [search, setSearch] = useState('');
  const [stockStatus, setStockStatus] = useState('all');
  const [expiryStatus, setExpiryStatus] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const limit = 10;

  const loadInventory = useCallback(async (targetPage = 1) => {
    setLoading(true);
    setError('');
    const params = new URLSearchParams({
      page: String(targetPage),
      limit: String(limit),
      search,
      stock_status: stockStatus,
      expiry_status: expiryStatus,
    });

    try {
      const [summaryResponse, itemsResponse] = await Promise.all([
        authFetch(`${API_URL}/inventory/summary`),
        authFetch(`${API_URL}/inventory/items?${params}`),
      ]);
      if (!summaryResponse.ok || !itemsResponse.ok) throw new Error('Inventory data could not be loaded');
      const [summaryData, itemsData] = await Promise.all([
        summaryResponse.json(),
        itemsResponse.json(),
      ]);
      setSummary(summaryData);
      setItems(itemsData.items);
      setTotal(itemsData.total);
      setPage(targetPage);
    } catch (err) {
      setError(err.message || 'Inventory data could not be loaded');
    } finally {
      setLoading(false);
    }
  }, [authFetch, expiryStatus, search, stockStatus]);

  useEffect(() => {
    // Refresh when authentication, filters, or a successful CSV import changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadInventory(1);
  }, [loadInventory, refreshKey]);

  const submitSearch = (event) => {
    event.preventDefault();
    setSearch(draftSearch.trim());
  };

  const cards = summary ? [
    ['Products', summary.total_products, 'text-cyan-300'],
    ['Units in stock', summary.total_units, 'text-slate-100'],
    ['Low stock', summary.low_stock_products, summary.low_stock_products ? 'text-amber-300' : 'text-emerald-300'],
    ['Expiring ≤90d', summary.expiring_batches, summary.expiring_batches ? 'text-amber-300' : 'text-emerald-300'],
    ['Expired batches', summary.expired_batches, summary.expired_batches ? 'text-red-300' : 'text-emerald-300'],
    ['Inventory cost', money.format(summary.cost_value), 'text-slate-100'],
    ['Retail value', money.format(summary.retail_value), 'text-emerald-300'],
    ['Potential margin', money.format(summary.potential_margin), 'text-cyan-300'],
  ] : [];

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-slate-100">Inventory overview</h2>
        <p className="text-sm text-slate-400 mt-1">Live stock, expiry risk, and inventory value for your pharmacy.</p>
      </div>

      {error && <div className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 text-sm">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {cards.map(([label, value, color]) => (
          <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
            <p className={`text-2xl font-semibold mt-2 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex flex-col lg:flex-row gap-3 justify-between">
          <form onSubmit={submitSearch} className="flex gap-2 flex-1 max-w-xl">
            <input
              value={draftSearch}
              onChange={(event) => setDraftSearch(event.target.value)}
              placeholder="Search product, generic, category, or batch"
              className="flex-1 bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
            />
            <button className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-md text-sm font-medium">Search</button>
          </form>
          <div className="flex gap-2">
            <select value={stockStatus} onChange={(event) => setStockStatus(event.target.value)} className="bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm">
              <option value="all">All stock</option>
              <option value="low_stock">Low stock</option>
              <option value="in_stock">In stock</option>
            </select>
            <select value={expiryStatus} onChange={(event) => setExpiryStatus(event.target.value)} className="bg-slate-950 border border-slate-700 rounded-md px-3 py-2 text-sm">
              <option value="all">All expiry</option>
              <option value="expiring">Expiring ≤90d</option>
              <option value="expired">Expired</option>
              <option value="valid">Valid &gt;90d</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-950/70 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Batch</th>
                <th className="px-4 py-3">Batch qty</th>
                <th className="px-4 py-3">Total stock</th>
                <th className="px-4 py-3">Expiry</th>
                <th className="px-4 py-3">Cost / Retail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {!loading && items.map((item) => {
                const expiry = expiryLabel(item.expiry_date);
                const lowStock = item.total_stock <= item.min_stock_level;
                return (
                  <tr key={item.batch_id} className="hover:bg-slate-800/40">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-200">{item.name}</p>
                      <p className="text-xs text-slate-500">{item.generic_name} · {item.category}</p>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">{item.batch_number}</td>
                    <td className="px-4 py-3">{item.quantity}</td>
                    <td className="px-4 py-3">
                      <span className={lowStock ? 'text-amber-300' : 'text-slate-200'}>{item.total_stock}</span>
                      <span className="text-xs text-slate-500"> / min {item.min_stock_level}</span>
                    </td>
                    <td className="px-4 py-3">
                      <p>{item.expiry_date}</p>
                      <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs ${expiry.className}`}>{expiry.text}</span>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      <p>{money.format(item.cost_price)}</p>
                      <p className="text-emerald-300">{money.format(item.retail_price)}</p>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {loading && <p className="text-center py-10 text-slate-500">Loading inventory…</p>}
          {!loading && items.length === 0 && <p className="text-center py-10 text-slate-500">No inventory matches these filters.</p>}
        </div>

        {total > limit && (
          <div className="p-4 border-t border-slate-800 flex justify-between items-center text-sm">
            <span className="text-slate-500">{total} batches</span>
            <div className="flex gap-2 items-center">
              <button onClick={() => loadInventory(page - 1)} disabled={page === 1 || loading} className="px-3 py-1 bg-slate-800 rounded disabled:opacity-40">Previous</button>
              <span className="text-slate-400">Page {page} of {Math.ceil(total / limit)}</span>
              <button onClick={() => loadInventory(page + 1)} disabled={page * limit >= total || loading} className="px-3 py-1 bg-slate-800 rounded disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
