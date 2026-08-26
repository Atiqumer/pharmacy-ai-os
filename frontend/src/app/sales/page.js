'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { getApiErrorMessage } from '@/lib/apiError';
import DashboardSidebar from '@/components/DashboardSidebar';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const money = new Intl.NumberFormat('en-PK', { style: 'currency', currency: 'PKR', maximumFractionDigits: 2 });

export default function SalesPage() {
  const { user, loading: authLoading, authFetch, logout, isAdmin } = useAuth();
  const router = useRouter();
  const [inventory, setInventory] = useState([]);
  const [sales, setSales] = useState([]);
  const [summary, setSummary] = useState(null);
  const [cart, setCart] = useState([{ product_id: '', quantity: 1, unit_price: '' }]);
  const [selectedSale, setSelectedSale] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [authLoading, router, user]);

  const products = useMemo(() => {
    const unique = new Map();
    inventory.forEach((item) => {
      if (!unique.has(item.product_id)) unique.set(item.product_id, {
        id: item.product_id, name: item.name, stock: item.total_stock, retail_price: item.retail_price,
      });
    });
    return [...unique.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [inventory]);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [inventoryRes, salesRes, summaryRes] = await Promise.all([
        authFetch(`${API_URL}/inventory/items?limit=100&expiry_status=all`),
        authFetch(`${API_URL}/sales?limit=50`),
        authFetch(`${API_URL}/reports/summary`),
      ]);
      const [inventoryData, salesData, summaryData] = await Promise.all([
        inventoryRes.json(), salesRes.json(), summaryRes.json(),
      ]);
      if (!inventoryRes.ok) throw new Error(getApiErrorMessage(inventoryData, 'Inventory could not be loaded'));
      if (!salesRes.ok) throw new Error(getApiErrorMessage(salesData, 'Sales could not be loaded'));
      if (!summaryRes.ok) throw new Error(getApiErrorMessage(summaryData, 'Sales summary could not be loaded'));
      setInventory(inventoryData.items);
      setSales(salesData.sales);
      setSummary(summaryData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) loadWorkspace();
  }, [loadWorkspace, user]);

  const updateCartLine = (index, field, value) => {
    setCart((current) => current.map((line, lineIndex) => {
      if (lineIndex !== index) return line;
      if (field === 'product_id') {
        const product = products.find((candidate) => candidate.id === value);
        return { ...line, product_id: value, unit_price: product?.retail_price ?? '' };
      }
      return { ...line, [field]: value };
    }));
  };

  const completeSale = async (event) => {
    event.preventDefault();
    const saleForm = event.currentTarget;
    setActionLoading(true);
    setError('');
    setSuccess('');
    const form = new FormData(saleForm);
    const payload = {
      items: cart.map((line) => ({
        product_id: line.product_id,
        quantity: Number(line.quantity),
        unit_price: line.unit_price === '' ? null : line.unit_price,
      })),
      discount: form.get('discount') || 0,
      notes: form.get('notes') || null,
    };
    try {
      const response = await authFetch(`${API_URL}/sales`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Sale could not be completed'));
      setSuccess(`${data.sale_number} completed for ${money.format(data.total)}`);
      setCart([{ product_id: '', quantity: 1, unit_price: '' }]);
      saleForm.reset();
      await loadWorkspace();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const openSale = async (saleId) => {
    setActionLoading(true);
    setError('');
    try {
      const response = await authFetch(`${API_URL}/sales/${saleId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Sale details could not be loaded'));
      setSelectedSale(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const returnItems = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    setError('');
    setSuccess('');
    const form = new FormData(event.currentTarget);
    const items = selectedSale.items.map((item) => ({
      sale_item_id: item.id,
      quantity: Number(form.get(`quantity_${item.id}`) || 0),
    })).filter((item) => item.quantity > 0);
    try {
      if (!items.length) throw new Error('Enter a return quantity for at least one item');
      const response = await authFetch(`${API_URL}/sales/${selectedSale.id}/returns`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: form.get('reason'), items }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Return could not be completed'));
      setSuccess(`${data.return_number} completed; refund ${money.format(data.refund_amount)}`);
      setSelectedSale(null);
      await loadWorkspace();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const downloadReport = async (path, fallbackName) => {
    setError('');
    try {
      const response = await authFetch(`${API_URL}${path}`);
      if (!response.ok) {
        const data = await response.json();
        throw new Error(getApiErrorMessage(data, 'Report could not be downloaded'));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fallbackName;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  if (authLoading || !user) return <main className="grid min-h-screen place-items-center bg-slate-100 text-sm text-slate-500">Loading…</main>;

  return (
    <DashboardSidebar user={user} isAdmin={isAdmin} onLogout={logout} authFetch={authFetch}>
    <main className="app-content min-h-screen px-4 py-6 md:px-7 md:py-7">
      <div className="mx-auto max-w-[1440px] space-y-7">
        <header className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 sm:flex-row">
          <div><h1 className="text-2xl font-semibold tracking-tight text-slate-950">Sales workspace</h1><p className="mt-1.5 text-sm text-slate-500">Checkout with FEFO batch allocation and auditable returns.</p></div>
          <div className="flex flex-wrap gap-2"><button onClick={() => downloadReport('/reports/inventory.csv', 'inventory.csv')} className="ui-secondary">Export inventory</button><button onClick={() => downloadReport('/reports/sales.csv', 'sales.csv')} className="ui-secondary">Export sales</button></div>
        </header>

        {error && <div role="alert" className="p-3 border border-red-500/30 bg-red-500/10 text-red-300 rounded-lg">{error}</div>}
        {success && <div className="p-3 border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 rounded-lg">{success}</div>}

        <div className="grid sm:grid-cols-3 gap-4">
          <Metric label="Sales (30 days)" value={summary ? money.format(summary.sales_total) : '—'} />
          <Metric label="Completed sales" value={summary?.sale_count ?? '—'} />
          <Metric label="Estimated gross profit" value={summary ? money.format(summary.estimated_gross_profit) : '—'} />
        </div>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4">New sale</h2>
          <form onSubmit={completeSale} className="space-y-4">
            {cart.map((line, index) => <div key={index} className="grid sm:grid-cols-[1fr_110px_150px_auto] gap-3 items-end">
              <label className="text-xs text-slate-400">Product<select required value={line.product_id} onChange={(event) => updateCartLine(index, 'product_id', event.target.value)} className="form-input"><option value="">Select product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} ({product.stock} in stock)</option>)}</select></label>
              <label className="text-xs text-slate-400">Quantity<input required type="number" min="1" value={line.quantity} onChange={(event) => updateCartLine(index, 'quantity', event.target.value)} className="form-input" /></label>
              <label className="text-xs text-slate-400">Unit price<input required type="number" min="0" step="0.01" value={line.unit_price} onChange={(event) => updateCartLine(index, 'unit_price', event.target.value)} className="form-input" /></label>
              <button type="button" disabled={cart.length === 1} onClick={() => setCart((current) => current.filter((_, i) => i !== index))} className="mb-2 text-red-300 disabled:opacity-30">Remove</button>
            </div>)}
            <button type="button" onClick={() => setCart((current) => [...current, { product_id: '', quantity: 1, unit_price: '' }])} className="text-sm text-cyan-300">+ Add item</button>
            <div className="grid sm:grid-cols-2 gap-3"><label className="text-sm text-slate-400">Discount<input name="discount" type="number" min="0" step="0.01" defaultValue="0" className="form-input" /></label><label className="text-sm text-slate-400">Note<input name="notes" maxLength="500" className="form-input" /></label></div>
            <div className="flex justify-end"><button disabled={actionLoading || loading} className="ui-primary">{actionLoading ? 'Processing…' : 'Complete sale'}</button></div>
          </form>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-5 border-b border-slate-800"><h2 className="text-lg font-semibold">Recent sales</h2></div>
          <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead className="bg-slate-950/70 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Sale</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Items</th><th className="px-4 py-3">Total</th><th className="px-4 py-3">Action</th></tr></thead><tbody className="divide-y divide-slate-800">{sales.map((sale) => <tr key={sale.id}><td className="px-4 py-3 font-mono text-xs">{sale.sale_number}</td><td className="px-4 py-3">{new Date(sale.created_at).toLocaleString()}</td><td className="px-4 py-3 capitalize">{sale.status.replace('_', ' ')}</td><td className="px-4 py-3">{sale.item_count}</td><td className="px-4 py-3 text-emerald-300">{money.format(sale.total)}</td><td className="px-4 py-3"><button disabled={actionLoading} onClick={() => openSale(sale.id)} className="text-cyan-300">View / return</button></td></tr>)}</tbody></table>{!loading && !sales.length && <p className="text-center py-10 text-slate-500">No sales yet.</p>}</div>
        </section>
      </div>

      {selectedSale && <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm grid place-items-center p-4"><div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 rounded-xl p-6"><div className="flex justify-between mb-5"><div><h2 className="text-xl font-semibold">{selectedSale.sale_number}</h2><p className="text-sm text-slate-400">Return sold items to their original batches.</p></div><button onClick={() => setSelectedSale(null)} className="text-slate-400">Close</button></div><form onSubmit={returnItems} className="space-y-4">{selectedSale.items.map((item) => { const remaining = item.quantity - item.returned_quantity; return <div key={item.id} className="grid sm:grid-cols-[1fr_130px] gap-3 border border-slate-800 rounded-lg p-3"><div><p className="font-medium">{item.product_name}</p><p className="text-xs text-slate-500">Batch {item.batch_number} · Sold {item.quantity} · Returned {item.returned_quantity}</p></div><label className="text-xs text-slate-400">Return quantity<input name={`quantity_${item.id}`} type="number" min="0" max={remaining} defaultValue="0" disabled={!remaining} className="form-input" /></label></div>; })}<label className="block text-sm text-slate-400">Return reason<textarea required name="reason" maxLength="500" className="form-input" /></label><div className="flex justify-end gap-2"><button type="button" onClick={() => setSelectedSale(null)} className="px-4 py-2 bg-slate-800 rounded-md">Cancel</button><button disabled={actionLoading || selectedSale.status === 'refunded'} className="px-4 py-2 bg-amber-600 rounded-md disabled:opacity-40">Complete return</button></div></form></div></div>}
    </main>
    </DashboardSidebar>
  );
}

function Metric({ label, value }) {
  return <div className="bg-slate-900 border border-slate-800 rounded-xl p-5"><p className="text-xs uppercase text-slate-500">{label}</p><p className="text-2xl mt-2 font-semibold">{value}</p></div>;
}
