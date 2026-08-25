'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { getApiErrorMessage } from '@/lib/apiError';
import DashboardSidebar from '@/components/DashboardSidebar';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const money = new Intl.NumberFormat('en-PK', { style: 'currency', currency: 'PKR', maximumFractionDigits: 0 });

export default function PurchasingPage() {
  const { user, loading: authLoading, authFetch, logout, isAdmin } = useAuth();
  const router = useRouter();
  const [suppliers, setSuppliers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [editingOrder, setEditingOrder] = useState(null);
  const [editingSupplier, setEditingSupplier] = useState(null);
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
    ['contact_name', 'phone', 'email', 'address'].forEach((field) => { if (!payload[field]) payload[field] = null; });
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
      const response = await authFetch(editingOrder ? `${API_URL}/purchasing/orders/${editingOrder.id}` : `${API_URL}/purchasing/orders`, {
        method: editingOrder ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Purchase order could not be created'));
      setShowOrderForm(false);
      setEditingOrder(null);
      setOrderLines([{ product_id: '', quantity: 1, cost_price: '' }]);
      await loadWorkspace();
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  const openEditOrder = async (orderId) => {
    setActionLoading(true);
    setError('');
    try {
      const response = await authFetch(`${API_URL}/purchasing/orders/${orderId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Order details could not be loaded'));
      setEditingOrder(data);
      setOrderLines(data.items.map((item) => ({ product_id: item.product_id, quantity: item.ordered_quantity, cost_price: item.cost_price })));
      setShowOrderForm(true);
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  const cancelOrder = async (orderId) => {
    if (!confirm('Cancel this purchase order?')) return;
    setActionLoading(true);
    setError('');
    try {
      const response = await authFetch(`${API_URL}/purchasing/orders/${orderId}/cancel`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Order could not be cancelled'));
      await loadWorkspace();
    } catch (err) { setError(err.message); } finally { setActionLoading(false); }
  };

  const updateSupplier = async (event) => {
    event.preventDefault();
    setActionLoading(true);
    setError('');
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    ['contact_name', 'phone', 'email', 'address'].forEach((field) => { if (!payload[field]) payload[field] = null; });
    try {
      const response = await authFetch(`${API_URL}/suppliers/${editingSupplier.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(getApiErrorMessage(data, 'Supplier could not be updated'));
      setEditingSupplier(null);
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

  if (authLoading || !user) return <main className="grid min-h-screen place-items-center bg-slate-100 text-sm text-slate-500">Loading…</main>;

  return (
    <DashboardSidebar user={user} isAdmin={isAdmin} onLogout={logout}>
    <main className="app-content min-h-screen px-4 py-6 md:px-7 md:py-7">
      <div className="mx-auto max-w-[1440px] space-y-7">
        <header className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-6 sm:flex-row">
          <div><h1 className="text-2xl font-semibold tracking-tight text-slate-950">Purchasing workspace</h1><p className="mt-1.5 text-sm text-slate-500">Suppliers, purchase orders, and goods receiving.</p></div>
          <div className="flex gap-2 items-end"><button onClick={() => setShowSupplierForm(true)} className="px-4 py-2 bg-slate-800 rounded-md text-sm">Add supplier</button><button onClick={() => { setEditingOrder(null); setOrderLines([{ product_id: '', quantity: 1, cost_price: '' }]); setShowOrderForm(true); }} disabled={!suppliers.length || !products.length} className="px-4 py-2 bg-emerald-600 rounded-md text-sm font-medium disabled:opacity-40">New purchase order</button></div>
        </header>

        {error && <div className="p-3 border border-red-500/30 bg-red-500/10 text-red-300 rounded-lg">{error}</div>}

        <div className="grid sm:grid-cols-3 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5"><p className="text-xs uppercase text-slate-500">Active suppliers</p><p className="text-3xl mt-2 font-semibold">{suppliers.length}</p></div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5"><p className="text-xs uppercase text-slate-500">Open orders</p><p className="text-3xl mt-2 font-semibold text-amber-300">{orders.filter((order) => !['received', 'cancelled'].includes(order.status)).length}</p></div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5"><p className="text-xs uppercase text-slate-500">On order value</p><p className="text-2xl mt-2 font-semibold text-cyan-300">{money.format(orders.filter((order) => !['received', 'cancelled'].includes(order.status)).reduce((sum, order) => sum + order.total_cost, 0))}</p></div>
        </div>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-5"><div className="flex justify-between mb-3"><h2 className="text-lg font-semibold">Suppliers</h2><span className="text-xs text-slate-500">{suppliers.length} active</span></div><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">{suppliers.map((supplier) => <div key={supplier.id} className="border border-slate-800 rounded-lg p-3"><div className="flex justify-between gap-2"><div><p className="font-medium">{supplier.name}</p><p className="text-xs text-slate-500">{supplier.contact_name || 'No contact'} · {supplier.phone || supplier.email || 'No details'}</p></div><button onClick={() => setEditingSupplier(supplier)} className="text-xs text-cyan-300">Edit</button></div></div>)}</div></section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-5 border-b border-slate-800"><h2 className="text-lg font-semibold">Purchase orders</h2></div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left"><thead className="bg-slate-950/70 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Order</th><th className="px-4 py-3">Supplier</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Received</th><th className="px-4 py-3">Expected</th><th className="px-4 py-3">Value</th><th className="px-4 py-3">Action</th></tr></thead>
              <tbody className="divide-y divide-slate-800">{orders.map((order) => <tr key={order.id}><td className="px-4 py-3 font-mono text-xs">{order.order_number}</td><td className="px-4 py-3">{order.supplier_name}</td><td className="px-4 py-3 capitalize">{order.status.replace('_', ' ')}</td><td className="px-4 py-3">{order.received_quantity} / {order.ordered_quantity}</td><td className="px-4 py-3">{order.expected_date || '—'}</td><td className="px-4 py-3">{money.format(order.total_cost)}</td><td className="px-4 py-3 space-x-2 whitespace-nowrap">{order.status === 'draft' && <><button disabled={actionLoading} onClick={() => openEditOrder(order.id)} className="text-slate-300">Edit</button><button disabled={actionLoading} onClick={() => submitOrder(order.id)} className="text-cyan-300">Submit</button></>}{['ordered', 'partially_received'].includes(order.status) && <button disabled={actionLoading} onClick={() => openReceipt(order.id)} className="text-emerald-300">Receive</button>}{['draft', 'ordered'].includes(order.status) && order.received_quantity === 0 && <button disabled={actionLoading} onClick={() => cancelOrder(order.id)} className="text-red-300">Cancel</button>}</td></tr>)}</tbody>
            </table>
            {!loading && !orders.length && <p className="text-center py-10 text-slate-500">No purchase orders yet.</p>}
            {loading && <p className="text-center py-10 text-slate-500">Loading purchasing data…</p>}
          </div>
        </section>
      </div>

      {showSupplierForm && <Modal title="Add supplier" onClose={() => setShowSupplierForm(false)}><form onSubmit={createSupplier} className="space-y-4"><label className="block text-sm text-slate-400">Supplier name<input required name="name" className="form-input" /></label><label className="block text-sm text-slate-400">Contact name<input name="contact_name" className="form-input" /></label><div className="grid grid-cols-2 gap-3"><label className="text-sm text-slate-400">Phone<input name="phone" className="form-input" /></label><label className="text-sm text-slate-400">Email<input type="email" name="email" className="form-input" /></label></div><label className="block text-sm text-slate-400">Address<textarea name="address" className="form-input" /></label><SubmitButtons loading={actionLoading} onCancel={() => setShowSupplierForm(false)} label="Create supplier" /></form></Modal>}

      {showOrderForm && <Modal title={editingOrder ? `Edit ${editingOrder.order_number}` : 'New purchase order'} onClose={() => { setShowOrderForm(false); setEditingOrder(null); }} wide><form onSubmit={createOrder} className="space-y-5"><div className="grid sm:grid-cols-2 gap-3"><label className="text-sm text-slate-400">Supplier<select required name="supplier_id" defaultValue={editingOrder?.supplier_id || ''} className="form-input"><option value="">Select supplier</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></label><label className="text-sm text-slate-400">Expected date<input type="date" name="expected_date" defaultValue={editingOrder?.expected_date || ''} className="form-input" /></label></div><div className="space-y-3">{orderLines.map((line, index) => <div key={index} className="grid grid-cols-[1fr_100px_120px_auto] gap-2 items-end"><label className="text-xs text-slate-400">Product<select required value={line.product_id} onChange={(event) => updateLine(index, 'product_id', event.target.value)} className="form-input"><option value="">Select product</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label><label className="text-xs text-slate-400">Quantity<input required min="1" type="number" value={line.quantity} onChange={(event) => updateLine(index, 'quantity', event.target.value)} className="form-input" /></label><label className="text-xs text-slate-400">Unit cost<input required min="0" step="0.01" type="number" value={line.cost_price} onChange={(event) => updateLine(index, 'cost_price', event.target.value)} className="form-input" /></label><button type="button" disabled={orderLines.length === 1} onClick={() => setOrderLines((current) => current.filter((_, lineIndex) => lineIndex !== index))} className="mb-2 text-red-300 disabled:opacity-30">Remove</button></div>)}</div><button type="button" onClick={() => setOrderLines((current) => [...current, { product_id: '', quantity: 1, cost_price: '' }])} className="text-sm text-cyan-300">+ Add product line</button><label className="block text-sm text-slate-400">Notes<textarea name="notes" defaultValue={editingOrder?.notes || ''} className="form-input" /></label><SubmitButtons loading={actionLoading} onCancel={() => { setShowOrderForm(false); setEditingOrder(null); }} label={editingOrder ? 'Save order' : 'Create draft order'} /></form></Modal>}

      {editingSupplier && <Modal title="Edit supplier" onClose={() => setEditingSupplier(null)}><form onSubmit={updateSupplier} className="space-y-4"><label className="block text-sm text-slate-400">Supplier name<input required name="name" defaultValue={editingSupplier.name} className="form-input" /></label><label className="block text-sm text-slate-400">Contact name<input name="contact_name" defaultValue={editingSupplier.contact_name || ''} className="form-input" /></label><div className="grid grid-cols-2 gap-3"><label className="text-sm text-slate-400">Phone<input name="phone" defaultValue={editingSupplier.phone || ''} className="form-input" /></label><label className="text-sm text-slate-400">Email<input type="email" name="email" defaultValue={editingSupplier.email || ''} className="form-input" /></label></div><label className="block text-sm text-slate-400">Address<textarea name="address" defaultValue={editingSupplier.address || ''} className="form-input" /></label><SubmitButtons loading={actionLoading} onCancel={() => setEditingSupplier(null)} label="Save supplier" /></form></Modal>}

      {receiptOrder && <Modal title={`Receive ${receiptOrder.order_number}`} onClose={() => setReceiptOrder(null)} wide><form onSubmit={receiveOrder} className="space-y-5"><label className="block text-sm text-slate-400">Supplier invoice/reference<input name="reference" className="form-input" /></label><div className="space-y-4">{receiptOrder.items.filter((item) => item.received_quantity < item.ordered_quantity).map((item) => { const remaining = item.ordered_quantity - item.received_quantity; return <div key={item.id} className="border border-slate-800 rounded-lg p-3"><p className="font-medium">{item.product_name} <span className="text-xs text-slate-500">({remaining} remaining)</span></p><div className="grid sm:grid-cols-4 gap-2 mt-2"><label className="text-xs text-slate-400">Receive qty<input required type="number" min="1" max={remaining} defaultValue={remaining} name={`quantity_${item.id}`} className="form-input" /></label><label className="text-xs text-slate-400">Batch number<input required name={`batch_${item.id}`} className="form-input" /></label><label className="text-xs text-slate-400">Expiry<input required type="date" name={`expiry_${item.id}`} className="form-input" /></label><label className="text-xs text-slate-400">Retail price<input required type="number" min="0" step="0.01" name={`retail_${item.id}`} className="form-input" /></label></div></div>; })}</div><label className="block text-sm text-slate-400">Receiving notes<textarea name="notes" className="form-input" /></label><SubmitButtons loading={actionLoading} onCancel={() => setReceiptOrder(null)} label="Post goods receipt" /></form></Modal>}
    </main>
    </DashboardSidebar>
  );
}

function Modal({ title, children, onClose, wide = false }) {
  return <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm grid place-items-center p-4"><div className={`w-full ${wide ? 'max-w-4xl' : 'max-w-lg'} max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 rounded-xl p-6`}><div className="flex justify-between mb-5"><h2 className="text-xl font-semibold">{title}</h2><button onClick={onClose} className="text-slate-400">Close</button></div>{children}</div></div>;
}

function SubmitButtons({ loading, onCancel, label }) {
  return <div className="flex justify-end gap-2"><button type="button" onClick={onCancel} className="px-4 py-2 bg-slate-800 rounded-md text-sm">Cancel</button><button disabled={loading} className="px-4 py-2 bg-emerald-600 rounded-md text-sm font-medium disabled:opacity-50">{loading ? 'Saving…' : label}</button></div>;
}
