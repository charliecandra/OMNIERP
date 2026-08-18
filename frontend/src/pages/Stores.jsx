import { useEffect, useState } from "react";
import { Storefront, CheckCircle, Circle } from "@phosphor-icons/react";
import api from "../lib/api";

const PLATFORM = {
  shopee: { color: "#FF5722", label: "Shopee" },
  tiktok: { color: "#00F2FE", label: "TikTok Shop" },
};

export default function Stores() {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/stores");
        setStores(data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div data-testid="stores-page">
      <header className="border-b border-white/10 px-8 py-6">
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">CONNECTIONS</div>
        <h1 className="font-heading text-3xl tracking-tight font-bold mt-1">Stores</h1>
      </header>

      <div className="p-8">
        {loading && <div className="text-zinc-500 font-mono text-xs uppercase tracking-widest">Loading…</div>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {stores.map((s) => {
            const p = PLATFORM[s.platform_name] || { color: "#FFFFFF", label: s.platform_name };
            return (
              <div key={s.id} data-testid={`store-card-${s.id}`} className="border border-white/10 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 flex items-center justify-center rounded-sm"
                      style={{ background: `${p.color}1a`, border: `1px solid ${p.color}55` }}
                    >
                      <Storefront size={20} weight="duotone" style={{ color: p.color }} />
                    </div>
                    <div>
                      <div className="font-heading font-bold text-lg tracking-tight">{s.store_name}</div>
                      <div className="text-[10px] font-mono uppercase tracking-widest" style={{ color: p.color }}>
                        {p.label}
                      </div>
                    </div>
                  </div>
                  <span className={`flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest ${s.is_active ? "text-[#34C759]" : "text-zinc-500"}`}>
                    {s.is_active ? <CheckCircle size={14} weight="fill" /> : <Circle size={14} />}
                    {s.is_active ? "ACTIVE" : "PAUSED"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 font-mono text-xs pt-4 border-t border-white/10">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500">Store ID</div>
                    <div className="mt-1 text-white">#{s.id}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500">Webhook</div>
                    <div className="mt-1 text-zinc-400 text-[10px]">/api/webhooks/orders</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
