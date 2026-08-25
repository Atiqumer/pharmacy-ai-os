'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { getApiErrorMessage } from '@/lib/apiError';

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
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">Inventory overview</h2>
          <p className="text-sm text-slate-400 mt-1">Live stock, expiry risk, and inventory value for your pharmacy.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={toggleMovements} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-md text-sm">
            {showMovements ? 'Hide history' : 'Movement history'}
          </button>
          <button onClick={() => setShowAddForm(true)} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-md text-sm font-medium">
            Add batch
          </button>
        </div>
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

      {reorderSuggestions.length > 0 && (
        <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5">
          <div className="flex justify-between items-start gap-4 mb-4">
            <div><h3 className="font-semibold text-amber-200">Reorder suggestions</h3><p className="text-xs text-slate-400 mt-1">Targets approximately twice the configured minimum stock level.</p></div>
            <Link href="/purchasing" className="text-sm text-cyan-300 whitespace-nowrap">Open purchasing →</Link>
          </div>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {reorderSuggestions.slice(0, 6).map((suggestion) => (
              <div key={suggestion.product_id} className="bg-slate-950/70 rounded-lg p-3 text-sm">
                <p className="font-medium">{suggestion.product_name}</p>
                <p className="text-xs text-slate-500">{suggestion.generic_name}</p>
                <div className="flex justify-between mt-3"><span className="text-slate-400">Stock {suggestion.current_stock} / min {suggestion.min_stock_level}</span><span className="font-semibold text-amber-300">Order {suggestion.suggested_quantity}</span></div>
                <p className="text-xs text-slate-500 mt-1">{suggestion.last_supplier || 'No previous supplier'}</p>
              </div>
            ))}
          </div>
        </div>
      )}

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
                <th className="px-4 py-3">Action</th>
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
                    <td className="px-4 py-3 space-x-2 whitespace-nowrap">
                      <button onClick={() => setAdjustingItem(item)} className="px-3 py-1.5 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 rounded text-xs">
                        Adjust
                      </button>
                      <button onClick={() => setEditingItem(item)} className="px-3 py-1.5 bg-slate-700/50 hover:bg-slate-700 text-slate-300 rounded text-xs">Edit</button>
                      {item.quantity === 0 && <button onClick={() => archiveItem('batch', item)} className="px-2 py-1.5 text-red-300 text-xs">Archive batch</button>}
                      {item.total_stock === 0 && <button onClick={() => archiveItem('product', item)} className="px-2 py-1.5 text-red-300 text-xs">Archive product</button>}
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

      {showMovements && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-800 flex justify-between">
            <div>
              <h3 className="font-semibold">Stock movement history</h3>
              <p className="text-xs text-slate-500 mt-1">Latest 25 of {movementTotal} audited movements</p>
            </div>
            <button onClick={loadMovements} className="text-sm text-cyan-300">Refresh</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-950/70 text-xs uppercase text-slate-500 text-left">
                <tr>
                  <th className="px-4 py-3">Date</th><th className="px-4 py-3">Product / Batch</th><th className="px-4 py-3">Change</th><th className="px-4 py-3">Balance</th><th className="px-4 py-3">Reason</th><th className="px-4 py-3">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {movements.map((movement) => (
                  <tr key={movement.id}>
                    <td className="px-4 py-3 text-xs text-slate-400">{new Date(movement.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3"><p>{movement.product_name}</p><p className="text-xs text-slate-500">{movement.batch_number}</p></td>
                    <td className={`px-4 py-3 font-semibold ${movement.quantity_change > 0 ? 'text-emerald-300' : 'text-red-300'}`}>{movement.quantity_change > 0 ? '+' : ''}{movement.quantity_change}</td>
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
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={createItem} className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-5">
            <div className="flex justify-between items-center">
              <div><h3 className="text-lg font-semibold">Add inventory batch</h3><p className="text-xs text-slate-500">Opening quantity will be recorded in the stock ledger.</p></div>
              <button type="button" onClick={() => setShowAddForm(false)} className="text-slate-400 hover:text-white">Close</button>
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
              <button type="button" onClick={() => setShowAddForm(false)} className="px-4 py-2 bg-slate-800 rounded-md text-sm">Cancel</button>
              <button disabled={actionLoading} className="px-4 py-2 bg-emerald-600 rounded-md text-sm font-medium disabled:opacity-50">{actionLoading ? 'Saving…' : 'Create batch'}</button>
            </div>
          </form>
        </div>
      )}

      {adjustingItem && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={adjustStock} className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-5">
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
              <button type="button" onClick={() => setAdjustingItem(null)} className="px-4 py-2 bg-slate-800 rounded-md text-sm">Cancel</button>
              <button disabled={actionLoading} className="px-4 py-2 bg-cyan-600 rounded-md text-sm font-medium disabled:opacity-50">{actionLoading ? 'Saving…' : 'Save adjustment'}</button>
            </div>
          </form>
        </div>
      )}

      {editingItem && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <form onSubmit={updateItem} className="w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-5">
            <div className="flex justify-between"><div><h3 className="text-lg font-semibold">Edit product and batch</h3><p className="text-xs text-slate-500">Stock quantity can only be changed through an audited adjustment or sale.</p></div><button type="button" onClick={() => setEditingItem(null)} className="text-slate-400">Close</button></div>
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
            <div className="flex justify-end gap-2"><button type="button" onClick={() => setEditingItem(null)} className="px-4 py-2 bg-slate-800 rounded-md text-sm">Cancel</button><button disabled={actionLoading} className="px-4 py-2 bg-emerald-600 rounded-md text-sm font-medium disabled:opacity-50">{actionLoading ? 'Saving…' : 'Save changes'}</button></div>
          </form>
        </div>
      )}
    </section>
  );
}
