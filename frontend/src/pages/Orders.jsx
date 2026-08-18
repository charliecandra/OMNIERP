import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Printer, FunnelSimple } from "@phosphor-icons/react";
import api from "../lib/api";

const PLATFORM_COLORS = {
  shopee: { bg: "rgba(255,87,34,0.1)", border: "rgba(255,87,34,0.3)", text: "#FF5722" },
  tiktok: { bg: "rgba(0,242,254,0.1)", border: "rgba(0,242,254,0.3)", text: "#00F2FE" },
};

const STATUS_COLORS = {
  pending:   "text-[#FFCC00] border-[#FFCC00]/40 bg-[#FFCC00]/10",
  packed:    "text-[#007AFF] border-[#007AFF]/40 bg-[#007AFF]/10",
  shipped:   "text-[#00F2FE] border-[#00F2FE]/40 bg-[#00F2FE]/10",
  delivered: "text-[#34C759] border-[#34C759]/40 bg-[#34C759]/10",
  cancelled: "text-[#FF3B30] border-[#FF3B30]/40 bg-[#FF3B30]/10",
};

const fmt = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(n);

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [platform, setPlatform] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/orders", { params: { platform: platform || undefined, status: status || undefined } });
      setOrders(data);
      setSelected(new Set());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [platform, status]);

  const toggle = (id) => {
    const n = new Set(selected);
    n.has(id) ? n.delete(id) : n.add(id);
    setSelected(n);
  };
  const toggleAll = () => {
    if (selected.size === orders.length) setSelected(new Set());
    else setSelected(new Set(orders.map((o) => o.id)));
  };

  const summary = useMemo(() => {
    const gmv = orders.reduce((s, o) => s + (o.status === "cancelled" ? 0 : o.total_revenue), 0);
    return { count: orders.length, gmv };
  }, [orders]);

  const printLabels = () => {
    if (!selected.size) return toast.error("Select at least one order");
    toast.success(`Queued ${selected.size} thermal labels for print`, {
      description: "Batch dispatched to /dev/thermal-printer (mock)",
    });
  };

  return (
    <div data-testid="orders-page">
      <header className="border-b border-white/10 px-8 py-6 flex items-center justify-between">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">OPERATIONS</div>
          <h1 className="font-heading text-3xl tracking-tight font-bold mt-1">Order Hub</h1>
        </div>
        <button
          data-testid="batch-print-btn"
          onClick={printLabels}
          className="flex items-center gap-2 bg-[#007AFF] hover:bg-[#0056B3] text-white font-semibold px-4 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors"
        >
          <Printer size={16} weight="bold" />
          Batch Print Thermal Labels
          {selected.size > 0 && <span className="font-mono bg-white/20 px-1.5 py-0.5 rounded-sm">{selected.size}</span>}
        </button>
      </header>

      {/* Filters */}
      <div className="px-8 py-4 border-b border-white/10 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 text-zinc-500">
          <FunnelSimple size={16} />
          <span className="text-[10px] font-mono uppercase tracking-widest">Filter</span>
        </div>

        <select
          data-testid="filter-platform"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm text-white [&>option]:bg-[#0A0A0A]"
        >
          <option value="">All Platforms</option>
          <option value="shopee">Shopee</option>
          <option value="tiktok">TikTok</option>
        </select>

        <select
          data-testid="filter-status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-1.5 text-xs font-mono uppercase tracking-widest rounded-sm text-white [&>option]:bg-[#0A0A0A]"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="packed">Packed</option>
          <option value="shipped">Shipped</option>
          <option value="delivered">Delivered</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <div className="ml-auto flex items-center gap-6 font-mono text-xs">
          <div><span className="text-zinc-500 uppercase tracking-widest text-[10px]">Orders</span> <span className="ml-2">{summary.count}</span></div>
          <div><span className="text-zinc-500 uppercase tracking-widest text-[10px]">GMV</span> <span className="ml-2 text-[#34C759]">{fmt(summary.gmv)}</span></div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="orders-table">
          <thead className="sticky top-0 backdrop-blur-md bg-[#0A0A0A]/80 border-b border-white/10">
            <tr className="text-left text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">
              <th className="p-4 w-10">
                <input type="checkbox" data-testid="orders-select-all"
                  checked={orders.length > 0 && selected.size === orders.length}
                  onChange={toggleAll}
                  className="accent-[#007AFF]" />
              </th>
              <th className="p-4">Order ID</th>
              <th className="p-4">Platform</th>
              <th className="p-4">Store</th>
              <th className="p-4">Status</th>
              <th className="p-4 text-right">Revenue</th>
              <th className="p-4 text-right">COGS</th>
              <th className="p-4 text-right">Profit</th>
              <th className="p-4">Date</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan="9" className="p-8 text-center text-zinc-500 font-mono text-xs uppercase tracking-widest">Loading…</td></tr>
            )}
            {!loading && orders.length === 0 && (
              <tr><td colSpan="9" className="p-8 text-center text-zinc-500 font-mono text-xs uppercase tracking-widest">No orders</td></tr>
            )}
            {orders.map((o) => {
              const p = PLATFORM_COLORS[o.platform_name] || PLATFORM_COLORS.shopee;
              const profit = o.total_revenue - o.total_cogs;
              return (
                <tr key={o.id} className="tbl-row border-b border-white/5" data-testid={`order-row-${o.id}`}>
                  <td className="p-4">
                    <input type="checkbox"
                      checked={selected.has(o.id)}
                      onChange={() => toggle(o.id)}
                      data-testid={`order-select-${o.id}`}
                      className="accent-[#007AFF]" />
                  </td>
                  <td className="p-4 font-mono text-xs">{o.marketplace_order_id}</td>
                  <td className="p-4">
                    <span
                      className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border rounded-sm"
                      style={{ background: p.bg, borderColor: p.border, color: p.text }}
                    >
                      {o.platform_name}
                    </span>
                  </td>
                  <td className="p-4 text-zinc-300">{o.store_name}</td>
                  <td className="p-4">
                    <span className={`text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border rounded-sm ${STATUS_COLORS[o.status] || ""}`}>
                      {o.status}
                    </span>
                  </td>
                  <td className="p-4 font-mono text-right">{fmt(o.total_revenue)}</td>
                  <td className="p-4 font-mono text-right text-zinc-400">{fmt(o.total_cogs)}</td>
                  <td className={`p-4 font-mono text-right ${profit >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>{fmt(profit)}</td>
                  <td className="p-4 font-mono text-xs text-zinc-400">
                    {new Date(o.order_date).toISOString().replace("T", " ").slice(0, 16)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
