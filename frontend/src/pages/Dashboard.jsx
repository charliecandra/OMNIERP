import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { CurrencyDollar, ShoppingBagOpen, TrendUp, ChartPieSlice } from "@phosphor-icons/react";
import api from "../lib/api";

const fmt = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n || 0);
const int = (n) => new Intl.NumberFormat("en-US").format(n || 0);

const PLATFORM_COLORS = { shopee: "#FF5722", tiktok: "#00F2FE" };

function KPI({ label, value, icon: Icon, accent, testid }) {
  return (
    <div
      data-testid={testid}
      className="border border-white/10 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">{label}</div>
          <div className={`font-heading font-black tracking-tighter text-4xl mt-3 ${accent || "text-white"}`}>
            <span className="font-mono">{value}</span>
          </div>
        </div>
        <Icon size={22} weight="duotone" className="text-zinc-600" />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/dashboard/metrics");
        setMetrics(data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="p-8 text-zinc-500 font-mono text-xs uppercase tracking-widest">Loading metrics…</div>;
  if (!metrics) return null;

  const chartData = metrics.per_store.map((s) => ({
    name: s.store_name.replace(/^Shopee |^TikTok /, ""),
    platform: s.platform_name,
    GMV: s.gmv,
    Profit: s.profit,
  }));

  return (
    <div data-testid="dashboard-page" className="min-h-screen">
      {/* Header */}
      <header className="border-b border-white/10 px-8 py-6 flex items-center justify-between">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">OVERVIEW</div>
          <h1 className="font-heading text-3xl tracking-tight font-bold mt-1">Command Center</h1>
        </div>
        <div className="text-right">
          <div className="text-xs font-mono uppercase tracking-widest text-zinc-500">Active stores</div>
          <div className="font-heading font-black text-xl">{metrics.per_store.length}</div>
        </div>
      </header>

      {/* KPI grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 border-b border-white/10">
        <KPI label="Total GMV"     value={fmt(metrics.total_gmv)}    icon={CurrencyDollar} testid="kpi-gmv" />
        <KPI label="Total Orders"  value={int(metrics.total_orders)} icon={ShoppingBagOpen} testid="kpi-orders" />
        <KPI label="Net Profit"    value={fmt(metrics.net_profit)}   icon={TrendUp} accent="text-[#34C759]" testid="kpi-profit" />
        <KPI label="Total COGS"    value={fmt(metrics.total_cogs)}   icon={ChartPieSlice} testid="kpi-cogs" />
      </div>

      {/* Chart + per-store table */}
      <div className="grid grid-cols-1 xl:grid-cols-3">
        <div className="xl:col-span-2 border-b xl:border-b-0 xl:border-r border-white/10 p-8">
          <div className="flex items-baseline justify-between mb-6">
            <div>
              <div className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">Store Performance</div>
              <h2 className="font-heading text-2xl tracking-tight font-bold mt-1">GMV vs Profit</h2>
            </div>
            <div className="flex gap-3 text-[10px] font-mono uppercase tracking-widest">
              <span className="flex items-center gap-2"><span className="w-2 h-2 bg-[#007AFF]" /> GMV</span>
              <span className="flex items-center gap-2"><span className="w-2 h-2 bg-[#34C759]" /> Profit</span>
            </div>
          </div>
          <div className="h-[340px]" data-testid="dashboard-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="#52525B" tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }} />
                <YAxis stroke="#52525B" tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }} />
                <Tooltip
                  contentStyle={{ background: "#0A0A0A", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 2, fontFamily: "JetBrains Mono", fontSize: 12 }}
                  cursor={{ fill: "rgba(255,255,255,0.03)" }}
                />
                <Bar dataKey="GMV" fill="#007AFF">
                  {chartData.map((d, i) => <Cell key={i} fill={PLATFORM_COLORS[d.platform] || "#007AFF"} fillOpacity={0.85} />)}
                </Bar>
                <Bar dataKey="Profit" fill="#34C759" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-8">
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500 mb-4">Per Store</div>
          <div className="space-y-3">
            {metrics.per_store.map((s) => (
              <div key={s.store_id} data-testid={`store-row-${s.store_id}`} className="border border-white/10 p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-heading font-bold text-sm truncate">{s.store_name}</div>
                  <span
                    className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded-sm border"
                    style={{
                      color: PLATFORM_COLORS[s.platform_name],
                      background: `${PLATFORM_COLORS[s.platform_name]}1a`,
                      borderColor: `${PLATFORM_COLORS[s.platform_name]}33`,
                    }}
                  >
                    {s.platform_name}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 font-mono text-xs">
                  <div><div className="text-zinc-500 text-[10px] uppercase tracking-widest">GMV</div><div className="mt-0.5">{fmt(s.gmv)}</div></div>
                  <div><div className="text-zinc-500 text-[10px] uppercase tracking-widest">Profit</div><div className="mt-0.5 text-[#34C759]">{fmt(s.profit)}</div></div>
                  <div><div className="text-zinc-500 text-[10px] uppercase tracking-widest">Orders</div><div className="mt-0.5">{int(s.orders)}</div></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
