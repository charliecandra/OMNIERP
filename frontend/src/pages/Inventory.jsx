import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Package, X, Check, PencilSimple } from "@phosphor-icons/react";
import api from "../lib/api";

const fmt = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(n || 0);
const int = (n) => new Intl.NumberFormat("en-US").format(n || 0);

function InboundModal({ open, onClose, skus, onSaved }) {
  const [skuId, setSkuId] = useState("");
  const [qty, setQty] = useState(100);
  const [baseCost, setBaseCost] = useState(0);
  const [shipping, setShipping] = useState(0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && skus.length && !skuId) setSkuId(String(skus[0].id));
  }, [open, skus, skuId]);

  const finalCogs = useMemo(() => {
    const q = Number(qty) || 0;
    const b = Number(baseCost) || 0;
    const s = Number(shipping) || 0;
    return q > 0 ? b + s / q : 0;
  }, [qty, baseCost, shipping]);

  if (!open) return null;

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/inventory/inbound", {
        master_sku_id: Number(skuId),
        quantity: Number(qty),
        base_cost: Number(baseCost),
        shipping_cost: Number(shipping),
      });
      toast.success("Inbound stock recorded");
      onSaved();
      onClose();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to record inbound");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <form onSubmit={submit} data-testid="inbound-modal" className="w-full max-w-lg bg-[#0A0A0A] border border-white/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Warehouse</div>
            <h3 className="font-heading text-xl tracking-tight font-bold mt-1">Add Inbound Stock</h3>
          </div>
          <button type="button" data-testid="inbound-close" onClick={onClose} className="text-zinc-500 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Master SKU</label>
            <select data-testid="inbound-sku" value={skuId} onChange={(e) => setSkuId(e.target.value)}
              className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white text-sm rounded-sm font-mono [&>option]:bg-[#0A0A0A]" required>
              {skus.map((s) => (<option key={s.id} value={s.id}>{s.master_sku_code} — {s.product_name}</option>))}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Quantity</label>
              <input data-testid="inbound-qty" type="number" min="1" value={qty} onChange={(e) => setQty(e.target.value)}
                className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm rounded-sm" required />
            </div>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Base Cost / unit</label>
              <input data-testid="inbound-base" type="number" step="0.01" min="0" value={baseCost} onChange={(e) => setBaseCost(e.target.value)}
                className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm rounded-sm" required />
            </div>
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Shipping (total)</label>
              <input data-testid="inbound-shipping" type="number" step="0.01" min="0" value={shipping} onChange={(e) => setShipping(e.target.value)}
                className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm rounded-sm" />
            </div>
          </div>
          <div className="border border-[#007AFF]/40 bg-[#007AFF]/10 p-4">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#007AFF]/80">FINAL BASE COST / UNIT</div>
            <div className="font-heading font-black text-3xl tracking-tighter mt-2 font-mono" data-testid="final-cogs">{fmt(finalCogs)}</div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mt-1">base + (shipping / quantity)</div>
          </div>
        </div>

        <div className="border-t border-white/10 px-6 py-4 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="border border-white/10 text-white hover:bg-white/5 px-4 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors">Cancel</button>
          <button data-testid="inbound-submit" type="submit" disabled={saving}
            className="bg-[#007AFF] hover:bg-[#0056B3] text-white font-semibold px-4 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors disabled:opacity-60">
            {saving ? "Saving…" : "Record Inbound"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ThresholdCell({ sku, onUpdated }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(sku.reorder_threshold);
  const [saving, setSaving] = useState(false);

  useEffect(() => { setValue(sku.reorder_threshold); }, [sku.reorder_threshold]);

  const commit = async () => {
    const n = Math.max(0, Number(value) || 0);
    if (n === sku.reorder_threshold) { setEditing(false); return; }
    setSaving(true);
    try {
      await api.patch(`/inventory/${sku.id}/threshold`, { reorder_threshold: n });
      toast.success("Threshold updated");
      onUpdated();
      setEditing(false);
    } catch {
      toast.error("Failed to update threshold");
    } finally { setSaving(false); }
  };

  if (!editing) {
    return (
      <button
        data-testid={`threshold-${sku.id}`}
        onClick={() => setEditing(true)}
        className="font-mono text-xs text-zinc-300 hover:text-white flex items-center gap-1.5 group"
        title="Click to edit reorder threshold"
      >
        {int(sku.reorder_threshold)}
        <PencilSimple size={11} className="opacity-0 group-hover:opacity-100 transition-opacity" />
      </button>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <input
        data-testid={`threshold-input-${sku.id}`}
        autoFocus type="number" min="0" value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setEditing(false); }}
        className="w-16 bg-transparent border border-[#007AFF] focus:ring-1 focus:ring-[#007AFF] outline-none px-1.5 py-0.5 text-white font-mono text-xs rounded-sm"
      />
      <button data-testid={`threshold-save-${sku.id}`} onClick={commit} disabled={saving} className="text-[#34C759] hover:opacity-80">
        <Check size={14} />
      </button>
    </div>
  );
}

export default function Inventory() {
  const [skus, setSkus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/inventory");
      setSkus(data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const totalUnits = skus.reduce((s, x) => s + x.real_stock, 0);
  const totalValue = skus.reduce((s, x) => s + x.real_stock * x.average_base_cost, 0);

  return (
    <div data-testid="inventory-page">
      <header className="border-b border-white/10 px-8 py-6 flex items-center justify-between">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">WAREHOUSE</div>
          <h1 className="font-heading text-3xl tracking-tight font-bold mt-1">Inventory</h1>
        </div>
        <button data-testid="open-inbound-modal" onClick={() => setModal(true)}
          className="flex items-center gap-2 bg-[#007AFF] hover:bg-[#0056B3] text-white font-semibold px-4 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors">
          <Plus size={16} weight="bold" /> Add Inbound Stock
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 border-b border-white/10">
        {[
          { k: "SKUs", v: skus.length, testid: "inv-total-skus" },
          { k: "Total Units on Hand", v: int(totalUnits), testid: "inv-total-units" },
          { k: "Inventory Value", v: fmt(totalValue), testid: "inv-total-value" },
        ].map((s, i) => (
          <div key={s.k} data-testid={s.testid} className={`p-6 ${i < 2 ? "border-r border-white/10" : ""}`}>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">{s.k}</div>
            <div className="font-heading font-black text-3xl tracking-tighter mt-2 font-mono">{s.v}</div>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="inventory-table">
          <thead className="sticky top-0 backdrop-blur-md bg-[#0A0A0A]/80 border-b border-white/10">
            <tr className="text-left text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
              <th className="p-4">SKU</th>
              <th className="p-4">Product</th>
              <th className="p-4 text-right">Stock</th>
              <th className="p-4 text-right">Reorder At</th>
              <th className="p-4 text-right">Avg Base Cost</th>
              <th className="p-4 text-right">Inventory Value</th>
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan="7" className="p-8 text-center text-zinc-500 font-mono text-xs uppercase tracking-widest">Loading…</td></tr>
            )}
            {skus.map((s) => {
              const neg = s.real_stock < 0;
              const low = !neg && s.real_stock <= s.reorder_threshold;
              return (
                <tr key={s.id} className="tbl-row border-b border-white/5" data-testid={`sku-row-${s.id}`}>
                  <td className="p-4 font-mono text-xs">{s.master_sku_code}</td>
                  <td className="p-4 text-zinc-200 flex items-center gap-2">
                    <Package size={14} className="text-zinc-500" />
                    {s.product_name}
                  </td>
                  <td className={`p-4 font-mono text-right ${neg ? "text-[#FF3B30]" : low ? "text-[#FFCC00]" : "text-white"}`}>
                    {int(s.real_stock)}
                  </td>
                  <td className="p-4 text-right">
                    <div className="inline-flex justify-end">
                      <ThresholdCell sku={s} onUpdated={load} />
                    </div>
                  </td>
                  <td className="p-4 font-mono text-right text-zinc-300">{fmt(s.average_base_cost)}</td>
                  <td className="p-4 font-mono text-right text-[#34C759]">{fmt(s.real_stock * s.average_base_cost)}</td>
                  <td className="p-4">
                    <span className={`text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border rounded-sm ${
                      neg ? "text-[#FF3B30] border-[#FF3B30]/40 bg-[#FF3B30]/10" :
                      low ? "text-[#FFCC00] border-[#FFCC00]/40 bg-[#FFCC00]/10" :
                            "text-[#34C759] border-[#34C759]/40 bg-[#34C759]/10"
                    }`}>
                      {neg ? "oversold" : low ? "reorder" : "healthy"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <InboundModal open={modal} onClose={() => setModal(false)} skus={skus} onSaved={load} />
    </div>
  );
}
