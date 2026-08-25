'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { getApiErrorMessage } from '@/lib/apiError';
import AppIcon from './AppIcon';

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
  if (days < 0) return { text: 'Expired', className: 'border-rose-200 bg-rose-50 text-rose-700' };
  if (days <= 90) return { text: `${days}d left`, className: 'border-amber-200 bg-amber-50 text-amber-700' };
  return { text: 'Valid', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' };
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
  const [showAddForm, setShowAddForm] = useState(false);
  const [adjustingItem, setAdjustingItem] = useState(null);
  const [editingItem, setEditingItem] = useState(null);
  const [showMovements, setShowMovements] = useState(false);
  const [movements, setMovements] = useState([]);
  const [movementTotal, setMovementTotal] = useState(0);
  const [reorderSuggestions, setReorderSuggestions] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);
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
      const [summaryResponse, itemsResponse, reorderResponse] = await Promise.all([
        authFetch(`${API_URL}/inventory/summary`),
        authFetch(`${API_URL}/inventory/items?${params}`),
        authFetch(`${API_URL}/analytics/reorder-suggestions`),
      ]);
      if (!summaryResponse.ok || !itemsResponse.ok || !reorderResponse.ok) throw new Error('Inventory data could not be loaded');
      const [summaryData, itemsData, reorderData] = await Promise.all([
        summaryResponse.json(), itemsResponse.json(), reorderResponse.json(),
      ]);
      setSummary(summaryData);
      setItems(itemsData.items);
      setTotal(itemsData.total);
      setReorderSuggestions(reorderData.suggestions);
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

  const createItem = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    setError('');
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    payload.quantity = Number(payload.quantity);
    payload.min_stock_level = Number(payload.min_stock_level);

    try {
      const response = await authFetch(`${API_URL}/inventory/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Inventory batch could not be created'));
      setShowAddForm(false);
      await loadInventory(1);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const adjustStock = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    setError('');
    const form = new FormData(event.currentTarget);
    const payload = {
      quantity_change: Number(form.get('quantity_change')),
      reason: form.get('reason'),
      note: form.get('note'),
    };

    try {
      const response = await authFetch(`${API_URL}/inventory/items/${adjustingItem.batch_id}/adjust`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Stock could not be adjusted'));
      setAdjustingItem(null);
      await loadInventory(page);
      if (showMovements) await loadMovements();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const updateItem = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    setError('');
    const form = new FormData(event.currentTarget);
    const productPayload = {
      name: form.get('name'), generic_name: form.get('generic_name'), category: form.get('category'),
      min_stock_level: Number(form.get('min_stock_level')), sku: form.get('sku'),
      barcode: form.get('barcode'), manufacturer: form.get('manufacturer'),
      strength: form.get('strength'), dosage_form: form.get('dosage_form'),
    };
    const batchPayload = {
      batch_number: form.get('batch_number'), cost_price: form.get('cost_price'),
      retail_price: form.get('retail_price'), expiry_date: form.get('expiry_date'),
    };
    try {
      const productResponse = await authFetch(`${API_URL}/inventory/products/${editingItem.product_id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(productPayload),
      });
      const productData = await productResponse.json();
      if (!productResponse.ok) throw new Error(getApiErrorMessage(productData, 'Product could not be updated'));
      const batchResponse = await authFetch(`${API_URL}/inventory/items/${editingItem.batch_id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(batchPayload),
      });
      const batchData = await batchResponse.json();
      if (!batchResponse.ok) throw new Error(getApiErrorMessage(batchData, 'Batch could not be updated'));
      setEditingItem(null);
      await loadInventory(page);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const archiveItem = async (kind, item) => {
    const label = kind === 'product' ? item.name : `${item.name} batch ${item.batch_number}`;
    if (!confirm(`Archive ${label}? It will be hidden from active inventory.`)) return;
    setActionLoading(true);
    setError('');
    const url = kind === 'product'
      ? `${API_URL}/inventory/products/${item.product_id}`
      : `${API_URL}/inventory/items/${item.batch_id}`;
    try {
      const response = await authFetch(url, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_active: false }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, `${kind} could not be archived`));
      await loadInventory(1);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const loadMovements = async () => {
    setError('');
    try {
      const response = await authFetch(`${API_URL}/inventory/movements?limit=25`);
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Stock history could not be loaded'));
      setMovements(data.movements);
      setMovementTotal(data.total);
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleMovements = async () => {
    const next = !showMovements;
    setShowMovements(next);
    if (next) await loadMovements();
  };

  const cards = summary ? [
    { label: 'Total products', value: summary.total_products, icon: 'package', tone: 'teal', hint: `${summary.total_units} units available` },
    { label: 'Inventory value', value: money.format(summary.retail_value), icon: 'wallet', tone: 'sky', hint: `${money.format(summary.cost_value)} at cost` },
    { label: 'Low stock', value: summary.low_stock_products, icon: 'alert', tone: summary.low_stock_products ? 'amber' : 'emerald', hint: summary.low_stock_products ? 'Needs attention' : 'Stock levels healthy' },
    { label: 'Expiring soon', value: summary.expiring_batches, icon: 'calendar', tone: summary.expiring_batches ? 'rose' : 'emerald', hint: `${summary.expired_batches} already expired` },
  ] : [];

  return (
    <section className="inventory-dashboard space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Inventory health</h2>
          <p className="mt-1 text-xs text-slate-500">Live stock, expiry risk, and current inventory value.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={toggleMovements} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50">
            <AppIcon name="history" className="h-4 w-4" /> {showMovements ? 'Hide history' : 'Movement history'}
          </button>
          <button onClick={() => setShowAddForm(true)} className="inline-flex items-center gap-2 rounded-lg bg-[#18324b] px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-[#10263a]">
            <AppIcon name="plus" className="h-4 w-4" /> Add stock batch
          </button>
        </div>
      </div>

      {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}

      <div className="glass-panel grid overflow-hidden rounded-lg border border-white/80 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="border-b border-slate-200 p-5 last:border-b-0 sm:[&:nth-child(odd)]:border-r xl:border-b-0 xl:border-r xl:last:border-r-0">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-medium text-slate-500">{card.label}</p>
              <AppIcon name={card.icon} className="h-[18px] w-[18px] text-slate-400" />
            </div>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{card.value}</p>
            <p className="mt-1.5 text-xs text-slate-500">{card.hint}</p>
          </div>
        ))}
      </div>

      {summary && <div className="glass-panel grid gap-px overflow-hidden rounded-lg border border-white/80 bg-slate-200/70 sm:grid-cols-3">
        <ValueStat label="Inventory cost" value={money.format(summary.cost_value)} />
        <ValueStat label="Potential sales" value={money.format(summary.retail_value)} />
        <ValueStat label="Potential margin" value={money.format(summary.potential_margin)} accent />
      </div>}

      {reorderSuggestions.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
          <div className="flex justify-between items-start gap-4 mb-4">
            <div><h3 className="font-bold text-amber-900">Reorder suggestions</h3><p className="mt-1 text-xs text-amber-800/70">Targets approximately twice the configured minimum stock level.</p></div>
            <Link href="/purchasing" className="inline-flex items-center gap-1 whitespace-nowrap text-sm font-semibold text-amber-800">Open purchasing <AppIcon name="arrow" className="h-4 w-4" /></Link>
          </div>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {reorderSuggestions.slice(0, 6).map((suggestion) => (
              <div key={suggestion.product_id} className="rounded-xl border border-amber-200/70 bg-white p-3.5 text-sm shadow-sm">
                <p className="font-semibold text-slate-900">{suggestion.product_name}</p>
                <p className="text-xs text-slate-500">{suggestion.generic_name}</p>
                <div className="mt-3 flex justify-between gap-3"><span className="text-slate-500">Stock {suggestion.current_stock} / min {suggestion.min_stock_level}</span><span className="font-bold text-amber-700">Order {suggestion.suggested_quantity}</span></div>
                <p className="mt-1 text-xs text-slate-400">{suggestion.last_supplier || 'No previous supplier'}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_12px_35px_rgba(15,23,42,0.06)]">
        <div className="flex flex-col justify-between gap-4 border-b border-slate-200 p-5 lg:flex-row lg:items-center">
          <div><h3 className="font-bold text-slate-900">Inventory management</h3><p className="mt-1 text-xs text-slate-500">Search, filter, and manage every active stock batch.</p></div>
          <form onSubmit={submitSearch} className="flex max-w-xl flex-1 gap-2 lg:ml-auto">
            <div className="relative min-w-0 flex-1">
              <AppIcon name="search" className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              value={draftSearch}
              onChange={(event) => setDraftSearch(event.target.value)}
              placeholder="Search product, generic, category, or batch"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-teal-400 focus:bg-white focus:ring-4 focus:ring-teal-50"
            />
            </div>
            <button className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800">Search</button>
          </form>
          <div className="flex gap-2 overflow-x-auto">
            <select aria-label="Stock status" value={stockStatus} onChange={(event) => setStockStatus(event.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 outline-none focus:border-teal-400">
              <option value="all">All stock</option>
              <option value="low_stock">Low stock</option>
              <option value="in_stock">In stock</option>
            </select>
            <select aria-label="Expiry status" value={expiryStatus} onChange={(event) => setExpiryStatus(event.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 outline-none focus:border-teal-400">
              <option value="all">All expiry</option>
              <option value="expiring">Expiring ≤90d</option>
              <option value="expired">Expired</option>
              <option value="valid">Valid &gt;90d</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-[0.08em] text-slate-500">
              <tr>
                <th className="px-4 py-3">Product</th>
                <th className="px-4 py-3">Batch</th>
                <th className="px-4 py-3">Batch qty</th>
                <th className="px-4 py-3">Total stock</th>
                <th className="px-4 py-3">Expiry</th>
                <th className="px-4 py-3">Cost / Retail</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {!loading && items.map((item) => {
                const expiry = expiryLabel(item.expiry_date);
                const lowStock = item.total_stock <= item.min_stock_level;
                return (
                  <tr key={item.batch_id} className="transition hover:bg-slate-50/80">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-900">{item.name}</p>
                      <p className="mt-0.5 text-xs text-slate-500">{item.generic_name} · {item.category}</p>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{item.batch_number}</td>
                    <td className="px-4 py-3">{item.quantity}</td>
                    <td className="px-4 py-3">
                      <span className={`font-semibold ${lowStock ? 'text-amber-700' : 'text-slate-900'}`}>{item.total_stock}</span>
                      <span className="text-xs text-slate-500"> / min {item.min_stock_level}</span>
                    </td>
                    <td className="px-4 py-3">
                      <p>{item.expiry_date}</p>
                      <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-[11px] font-semibold ${expiry.className}`}>{expiry.text}</span>
                    </td>
                    <td className="px-4 py-3 text-xs">
                      <p>{money.format(item.cost_price)}</p>
                      <p className="font-semibold text-emerald-700">{money.format(item.retail_price)}</p>
                    </td>
                    <td className="px-4 py-3 space-x-2 whitespace-nowrap">
                      <button onClick={() => setAdjustingItem(item)} className="rounded-lg bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-700 hover:bg-teal-100">
                        Adjust
                      </button>
                      <button onClick={() => setEditingItem(item)} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">Edit</button>
                      {item.quantity === 0 && <button onClick={() => archiveItem('batch', item)} className="px-2 py-1.5 text-xs font-semibold text-rose-600">Archive batch</button>}
                      {item.total_stock === 0 && <button onClick={() => archiveItem('product', item)} className="px-2 py-1.5 text-xs font-semibold text-rose-600">Archive product</button>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {loading && <p className="py-12 text-center text-sm text-slate-500">Loading inventory…</p>}
          {!loading && items.length === 0 && <p className="py-12 text-center text-sm text-slate-500">No inventory matches these filters.</p>}
        </div>

        {total > limit && (
          <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/70 p-4 text-sm">
            <span className="text-slate-500">{total} batches</span>
            <div className="flex gap-2 items-center">
              <button onClick={() => loadInventory(page - 1)} disabled={page === 1 || loading} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-medium disabled:opacity-40">Previous</button>
              <span className="text-slate-400">Page {page} of {Math.ceil(total / limit)}</span>
              <button onClick={() => loadInventory(page + 1)} disabled={page * limit >= total || loading} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 font-medium disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {showMovements && (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_12px_35px_rgba(15,23,42,0.06)]">
          <div className="flex justify-between border-b border-slate-200 p-5">
            <div>
              <h3 className="font-bold text-slate-900">Stock movement history</h3>
              <p className="mt-1 text-xs text-slate-500">Latest 25 of {movementTotal} audited movements</p>
            </div>
            <button onClick={loadMovements} className="text-sm font-semibold text-teal-700">Refresh</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Date</th><th className="px-4 py-3">Product / Batch</th><th className="px-4 py-3">Change</th><th className="px-4 py-3">Balance</th><th className="px-4 py-3">Reason</th><th className="px-4 py-3">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {movements.map((movement) => (
                  <tr key={movement.id}>
                    <td className="px-4 py-3 text-xs text-slate-400">{new Date(movement.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3"><p>{movement.product_name}</p><p className="text-xs text-slate-500">{movement.batch_number}</p></td>
                    <td className={`px-4 py-3 font-semibold ${movement.quantity_change > 0 ? 'text-emerald-700' : 'text-rose-600'}`}>{movement.quantity_change > 0 ? '+' : ''}{movement.quantity_change}</td>
                    <td className="px-4 py-3">{movement.quantity_before} → {movement.quantity_after}</td>
                    <td className="px-4 py-3 capitalize">{movement.reason}</td>
                    <td className="px-4 py-3 text-slate-400">{movement.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {movements.length === 0 && <p className="text-center py-8 text-slate-500">No stock movements recorded yet.</p>}
          </div>
        </div>
      )}

      {showAddForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm">
          <form onSubmit={createItem} className="max-h-[90vh] w-full max-w-2xl space-y-5 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 text-slate-800 shadow-2xl">
            <div className="flex justify-between items-center">
              <div><h3 className="text-lg font-semibold">Add inventory batch</h3><p className="text-xs text-slate-500">Opening quantity will be recorded in the stock ledger.</p></div>
              <button type="button" onClick={() => setShowAddForm(false)} className="text-sm font-semibold text-slate-500 hover:text-slate-900">Close</button>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <label className="text-sm text-slate-400">Product name<input required name="product_name" className="form-input" /></label>
              <label className="text-sm text-slate-400">Generic name<input required name="generic_name" className="form-input" /></label>
              <label className="text-sm text-slate-400">Category<input required name="category" className="form-input" /></label>
              <label className="text-sm text-slate-400">Supplier<input required name="supplier_name" defaultValue="Default Supplier" className="form-input" /></label>
              <label className="text-sm text-slate-400">Batch number<input required name="batch_number" className="form-input" /></label>
              <label className="text-sm text-slate-400">Expiry date<input required type="date" name="expiry_date" className="form-input" /></label>
              <label className="text-sm text-slate-400">Opening quantity<input required type="number" min="0" name="quantity" defaultValue="0" className="form-input" /></label>
              <label className="text-sm text-slate-400">Minimum stock<input required type="number" min="0" name="min_stock_level" defaultValue="10" className="form-input" /></label>
              <label className="text-sm text-slate-400">Cost price<input required type="number" min="0" step="0.01" name="cost_price" className="form-input" /></label>
              <label className="text-sm text-slate-400">Retail price<input required type="number" min="0" step="0.01" name="retail_price" className="form-input" /></label>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowAddForm(false)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">Cancel</button>
              <button disabled={actionLoading} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{actionLoading ? 'Saving…' : 'Create batch'}</button>
            </div>
          </form>
        </div>
      )}

      {adjustingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm">
          <form onSubmit={adjustStock} className="w-full max-w-md space-y-5 rounded-2xl border border-slate-200 bg-white p-6 text-slate-800 shadow-2xl">
            <div>
              <h3 className="text-lg font-semibold">Adjust stock</h3>
              <p className="text-sm text-slate-400 mt-1">{adjustingItem.name} · {adjustingItem.batch_number}</p>
              <p className="text-xs text-slate-500">Current batch quantity: {adjustingItem.quantity}</p>
            </div>
            <label className="block text-sm text-slate-400">Quantity change
              <input required type="number" name="quantity_change" placeholder="Use -3 for a sale, +10 for purchase" className="form-input" />
            </label>
            <label className="block text-sm text-slate-400">Reason
              <select required name="reason" className="form-input">
                <option value="purchase">Purchase received</option><option value="sale">Sale</option><option value="return">Return</option><option value="damage">Damaged</option><option value="expired">Expired</option><option value="correction">Stock count correction</option><option value="other">Other</option>
              </select>
            </label>
            <label className="block text-sm text-slate-400">Note<textarea name="note" maxLength="500" rows="3" className="form-input" /></label>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setAdjustingItem(null)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">Cancel</button>
              <button disabled={actionLoading} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{actionLoading ? 'Saving…' : 'Save adjustment'}</button>
            </div>
          </form>
        </div>
      )}

      {editingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm">
          <form onSubmit={updateItem} className="max-h-[90vh] w-full max-w-3xl space-y-5 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 text-slate-800 shadow-2xl">
            <div className="flex justify-between"><div><h3 className="text-lg font-semibold">Edit product and batch</h3><p className="text-xs text-slate-500">Stock quantity can only be changed through an audited adjustment or sale.</p></div><button type="button" onClick={() => setEditingItem(null)} className="text-sm font-semibold text-slate-500">Close</button></div>
            <div className="grid sm:grid-cols-2 gap-4">
              <label className="text-sm text-slate-400">Product name<input required name="name" defaultValue={editingItem.name} className="form-input" /></label>
              <label className="text-sm text-slate-400">Generic name<input required name="generic_name" defaultValue={editingItem.generic_name} className="form-input" /></label>
              <label className="text-sm text-slate-400">Category<input required name="category" defaultValue={editingItem.category} className="form-input" /></label>
              <label className="text-sm text-slate-400">Minimum stock<input required type="number" min="0" name="min_stock_level" defaultValue={editingItem.min_stock_level} className="form-input" /></label>
              <label className="text-sm text-slate-400">SKU<input name="sku" defaultValue={editingItem.sku || ''} className="form-input" /></label>
              <label className="text-sm text-slate-400">Barcode<input name="barcode" defaultValue={editingItem.barcode || ''} className="form-input" /></label>
              <label className="text-sm text-slate-400">Manufacturer<input name="manufacturer" defaultValue={editingItem.manufacturer || ''} className="form-input" /></label>
              <label className="text-sm text-slate-400">Strength<input name="strength" defaultValue={editingItem.strength || ''} className="form-input" /></label>
              <label className="text-sm text-slate-400">Dosage form<input name="dosage_form" defaultValue={editingItem.dosage_form || ''} className="form-input" /></label>
              <label className="text-sm text-slate-400">Batch number<input required name="batch_number" defaultValue={editingItem.batch_number} className="form-input" /></label>
              <label className="text-sm text-slate-400">Expiry date<input required type="date" name="expiry_date" defaultValue={editingItem.expiry_date} className="form-input" /></label>
              <label className="text-sm text-slate-400">Cost price<input required type="number" min="0" step="0.01" name="cost_price" defaultValue={editingItem.cost_price} className="form-input" /></label>
              <label className="text-sm text-slate-400">Retail price<input required type="number" min="0" step="0.01" name="retail_price" defaultValue={editingItem.retail_price} className="form-input" /></label>
            </div>
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setEditingItem(null)} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">Cancel</button><button disabled={actionLoading} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{actionLoading ? 'Saving…' : 'Save changes'}</button></div>
          </form>
        </div>
      )}
    </section>
  );
}

function ValueStat({ label, value, accent = false }) {
  return <div className="bg-white/65 px-5 py-4"><p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-400">{label}</p><p className={`mt-1 text-lg font-semibold ${accent ? 'text-[#18324b]' : 'text-slate-800'}`}>{value}</p></div>;
}
