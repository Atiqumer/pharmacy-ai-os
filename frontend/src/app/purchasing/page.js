'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { getApiErrorMessage } from '@/lib/apiError';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const money = new Intl.NumberFormat('en-PK', { style: 'currency', currency: 'PKR', maximumFractionDigits: 0 });

export default function PurchasingPage() {
  const { user, loading: authLoading, authFetch } = useAuth();
  const router = useRouter();
  const [suppliers, setSuppliers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [receiptOrder, setReceiptOrder] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [orderLines, setOrderLines] = useState([{ product_id: '', quantity: 1, cost_price: '' }]);

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [authLoading, router, user]);

  const products = useMemo(() => {
    const unique = new Map();
    inventory.forEach((item) => unique.set(item.product_id, { id: item.product_id, name: item.name }));
    return [...unique.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [inventory]);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [supplierRes, orderRes, inventoryRes] = await Promise.all([
        authFetch(`${API_URL}/suppliers`),
        authFetch(`${API_URL}/purchasing/orders?limit=100`),
        authFetch(`${API_URL}/inventory/items?limit=100`),
      ]);
      if (!supplierRes.ok || !orderRes.ok || !inventoryRes.ok) throw new Error('Purchasing workspace could not be loaded');
      const [supplierData, orderData, inventoryData] = await Promise.all([
        supplierRes.json(), orderRes.json(), inventoryRes.json(),
      ]);
      setSuppliers(supplierData.suppliers);
      setOrders(orderData.orders);
      setInventory(inventoryData.items);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    if (!user) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadWorkspace();
  }, [loadWorkspace, user]);

  const createSupplier = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const response = await authFetch(`${API_URL}/suppliers`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Supplier could not be created'));
      setShowSupplierForm(false);
      await loadWorkspace();
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  const createOrder = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    const form = new FormData(event.currentTarget);
    const items = orderLines.map((line) => ({
      product_id: line.product_id,
      quantity: Number(line.quantity),
      cost_price: line.cost_price,
    }));
    const payload = {
      supplier_id: form.get('supplier_id'),
      expected_date: form.get('expected_date') || null,
      notes: form.get('notes') || null,
      items,
    };
    try {
      const response = await authFetch(`${API_URL}/purchasing/orders`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Purchase order could not be created'));
      setShowOrderForm(false);
      setOrderLines([{ product_id: '', quantity: 1, cost_price: '' }]);
      await loadWorkspace();
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  const updateLine = (index, field, value) => {
    setOrderLines((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, [field]: value } : line));
  };

  const submitOrder = async (orderId) => {
    setActionLoading(true);
    try {
      const response = await authFetch(`${API_URL}/purchasing/orders/${orderId}/submit`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Order could not be submitted'));
      await loadWorkspace();
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  const openReceipt = async (orderId) => {
    setActionLoading(true);
    try {
      const response = await authFetch(`${API_URL}/purchasing/orders/${orderId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Order details could not be loaded'));
      setReceiptOrder(data);
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  const receiveOrder = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    const form = new FormData(event.currentTarget);
    const items = receiptOrder.items.map((item) => ({
      purchase_order_item_id: item.id,
      quantity: Number(form.get(`quantity_${item.id}`)),
      batch_number: form.get(`batch_${item.id}`),
      expiry_date: form.get(`expiry_${item.id}`),
      retail_price: form.get(`retail_${item.id}`),
    })).filter((line) => line.quantity > 0);
    try {
      const response = await authFetch(`${API_URL}/purchasing/orders/${receiptOrder.id}/receive`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference: form.get('reference') || null, notes: form.get('notes') || null, items }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Goods receipt could not be posted'));
      setReceiptOrder(null);
      await loadWorkspace();
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  if (authLoading || !user) return <main className="min-h-screen bg-slate-950 grid place-items-center text-slate-400">Loading…</main>;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-7">
        <header className="flex flex-col sm:flex-row justify-between gap-4 border-b border-slate-800 pb-5">
          <div><Link href="/" className="text-sm text-cyan-300">← Inventory dashboard</Link><h1 className="text-3xl font-bold mt-2">Purchasing</h1><p className="text-slate-400 mt-1">Suppliers, purchase orders, and goods receiving.</p></div>
          <div className="flex gap-2 items-end"><button onClick={() => setShowSupplierForm(true)} className="px-4 py-2 bg-slate-800 rounded-md text-sm">Add supplier</button><button onClick={() => setShowOrderForm(true)} disabled={!suppliers.length || !products.length} className="px-4 py-2 bg-emerald-600 rounded-md text-sm font-medium disabled:opacity-40">New purchase order</button></div>
        </header>

        {error && <div className="p-3 border border-red-500/30 bg-red-500/10 text-red-300 rounded-lg">{error}</div>}

        <div className="grid sm:grid-cols-3 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5"><p className="text-xs uppercase text-slate-500">Active suppliers</p><p className="text-3xl mt-2 font-semibold">{suppliers.length}</p></div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5"><p className="text-xs uppercase text-slate-500">Open orders</p><p className="text-3xl mt-2 font-semibold text-amber-300">{orders.filter((order) => !['received', 'cancelled'].includes(order.status)).length}</p></div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5"><p className="text-xs uppercase text-slate-500">On order value</p><p className="text-2xl mt-2 font-semibold text-cyan-300">{money.format(orders.filter((order) => !['received', 'cancelled'].includes(order.status)).reduce((sum, order) => sum + order.total_cost, 0))}</p></div>
        </div>

        <section className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-5 border-b border-slate-800"><h2 className="text-lg font-semibold">Purchase orders</h2></div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left"><thead className="bg-slate-950/70 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Order</th><th className="px-4 py-3">Supplier</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Received</th><th className="px-4 py-3">Expected</th><th className="px-4 py-3">Value</th><th className="px-4 py-3">Action</th></tr></thead>
              <tbody className="divide-y divide-slate-800">{orders.map((order) => <tr key={order.id}><td className="px-4 py-3 font-mono text-xs">{order.order_number}</td><td className="px-4 py-3">{order.supplier_name}</td><td className="px-4 py-3 capitalize">{order.status.replace('_', ' ')}</td><td className="px-4 py-3">{order.received_quantity} / {order.ordered_quantity}</td><td className="px-4 py-3">{order.expected_date || '—'}</td><td className="px-4 py-3">{money.format(order.total_cost)}</td><td className="px-4 py-3 space-x-2">{order.status === 'draft' && <button disabled={actionLoading} onClick={() => submitOrder(order.id)} className="text-cyan-300">Submit</button>}{['ordered', 'partially_received'].includes(order.status) && <button disabled={actionLoading} onClick={() => openReceipt(order.id)} className="text-emerald-300">Receive</button>}</td></tr>)}</tbody>
            </table>
            {!loading && !orders.length && <p className="text-center py-10 text-slate-500">No purchase orders yet.</p>}
            {loading && <p className="text-center py-10 text-slate-500">Loading purchasing data…</p>}
          </div>
        </section>
      </div>

      {showSupplierForm && <Modal title="Add supplier" onClose={() => setShowSupplierForm(false)}><form onSubmit={createSupplier} className="space-y-4"><label className="block text-sm text-slate-400">Supplier name<input required name="name" className="form-input" /></label><label className="block text-sm text-slate-400">Contact name<input name="contact_name" className="form-input" /></label><div className="grid grid-cols-2 gap-3"><label className="text-sm text-slate-400">Phone<input name="phone" className="form-input" /></label><label className="text-sm text-slate-400">Email<input type="email" name="email" className="form-input" /></label></div><label className="block text-sm text-slate-400">Address<textarea name="address" className="form-input" /></label><SubmitButtons loading={actionLoading} onCancel={() => setShowSupplierForm(false)} label="Create supplier" /></form></Modal>}

      {showOrderForm && <Modal title="New purchase order" onClose={() => setShowOrderForm(false)} wide><form onSubmit={createOrder} className="space-y-5"><div className="grid sm:grid-cols-2 gap-3"><label className="text-sm text-slate-400">Supplier<select required name="supplier_id" className="form-input"><option value="">Select supplier</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></label><label className="text-sm text-slate-400">Expected date<input type="date" name="expected_date" className="form-input" /></label></div><div className="space-y-3">{orderLines.map((line, index) => <div key={index} className="grid grid-cols-[1fr_100px_120px_auto] gap-2 items-end"><label className="text-xs text-slate-400">Product<select required value={line.product_id} onChange={(event) => updateLine(index, 'product_id', event.target.value)} className="form-input"><option value="">Select product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label><label className="text-xs text-slate-400">Quantity<input required min="1" type="number" value={line.quantity} onChange={(event) => updateLine(index, 'quantity', event.target.value)} className="form-input" /></label><label className="text-xs text-slate-400">Unit cost<input required min="0" step="0.01" type="number" value={line.cost_price} onChange={(event) => updateLine(index, 'cost_price', event.target.value)} className="form-input" /></label><button type="button" disabled={orderLines.length === 1} onClick={() => setOrderLines((current) => current.filter((_, lineIndex) => lineIndex !== index))} className="mb-2 text-red-300 disabled:opacity-30">Remove</button></div>)}</div><button type="button" onClick={() => setOrderLines((current) => [...current, { product_id: '', quantity: 1, cost_price: '' }])} className="text-sm text-cyan-300">+ Add product line</button><label className="block text-sm text-slate-400">Notes<textarea name="notes" className="form-input" /></label><SubmitButtons loading={actionLoading} onCancel={() => setShowOrderForm(false)} label="Create draft order" /></form></Modal>}

      {receiptOrder && <Modal title={`Receive ${receiptOrder.order_number}`} onClose={() => setReceiptOrder(null)} wide><form onSubmit={receiveOrder} className="space-y-5"><label className="block text-sm text-slate-400">Supplier invoice/reference<input name="reference" className="form-input" /></label><div className="space-y-4">{receiptOrder.items.filter((item) => item.received_quantity < item.ordered_quantity).map((item) => { const remaining = item.ordered_quantity - item.received_quantity; return <div key={item.id} className="border border-slate-800 rounded-lg p-3"><p className="font-medium">{item.product_name} <span className="text-xs text-slate-500">({remaining} remaining)</span></p><div className="grid sm:grid-cols-4 gap-2 mt-2"><label className="text-xs text-slate-400">Receive qty<input required type="number" min="1" max={remaining} defaultValue={remaining} name={`quantity_${item.id}`} className="form-input" /></label><label className="text-xs text-slate-400">Batch number<input required name={`batch_${item.id}`} className="form-input" /></label><label className="text-xs text-slate-400">Expiry<input required type="date" name={`expiry_${item.id}`} className="form-input" /></label><label className="text-xs text-slate-400">Retail price<input required type="number" min="0" step="0.01" name={`retail_${item.id}`} className="form-input" /></label></div></div>; })}</div><label className="block text-sm text-slate-400">Receiving notes<textarea name="notes" className="form-input" /></label><SubmitButtons loading={actionLoading} onCancel={() => setReceiptOrder(null)} label="Post goods receipt" /></form></Modal>}
    </main>
  );
}

function Modal({ title, children, onClose, wide = false }) {
  return <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm grid place-items-center p-4"><div className={`w-full ${wide ? 'max-w-4xl' : 'max-w-lg'} max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 rounded-xl p-6`}><div className="flex justify-between mb-5"><h2 className="text-xl font-semibold">{title}</h2><button onClick={onClose} className="text-slate-400">Close</button></div>{children}</div></div>;
}

function SubmitButtons({ loading, onCancel, label }) {
  return <div className="flex justify-end gap-2"><button type="button" onClick={onCancel} className="px-4 py-2 bg-slate-800 rounded-md text-sm">Cancel</button><button disabled={loading} className="px-4 py-2 bg-emerald-600 rounded-md text-sm font-medium disabled:opacity-50">{loading ? 'Saving…' : label}</button></div>;
}
