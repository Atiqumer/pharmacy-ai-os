import AppIcon from './AppIcon';

export default function AuthLayout({ title, description, children }) {
  return (
    <main className="auth-shell min-h-screen text-slate-900 lg:grid lg:grid-cols-[minmax(320px,0.8fr)_1.2fr]">
      <section className="hidden bg-[#18324b] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <Brand inverse />
        <div className="max-w-md">
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-300">Pharmacy operations</p>
          <h2 className="mt-4 text-3xl font-semibold leading-tight">Keep stock, purchases, and daily sales under control.</h2>
          <div className="mt-8 space-y-4 text-sm text-slate-300">
            <Feature icon="inventory" text="Batch-level inventory and expiry tracking" />
            <Feature icon="sales" text="Audited sales, returns, and stock movements" />
            <Feature icon="purchasing" text="Supplier and purchase-order management" />
          </div>
        </div>
        <p className="text-xs text-slate-400">RxOS pilot workspace</p>
      </section>
      <section className="flex min-h-screen items-center justify-center p-5 sm:p-10">
        <div className="w-full max-w-[420px]">
          <div className="mb-8 lg:hidden"><Brand /></div>
          <div className="glass-auth-card border border-white/80 p-6 sm:p-8">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950">{title}</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
            <div className="mt-7">{children}</div>
          </div>
        </div>
      </section>
    </main>
  );
}

function Brand({ inverse = false }) {
  return <div className="flex items-center gap-3"><div className={`grid h-9 w-9 place-items-center rounded-md border text-xl font-semibold ${inverse ? 'border-white/20 bg-white/10 text-white' : 'border-slate-200 bg-white text-[#18324b]'}`}>+</div><div><p className={`text-lg font-bold tracking-tight ${inverse ? 'text-white' : 'text-slate-900'}`}>RxOS</p><p className={`text-[10px] font-medium uppercase tracking-[0.16em] ${inverse ? 'text-slate-300' : 'text-slate-500'}`}>Pharmacy system</p></div></div>;
}

function Feature({ icon, text }) {
  return <div className="flex items-center gap-3"><AppIcon name={icon} className="h-5 w-5 text-slate-300" /><span>{text}</span></div>;
}
