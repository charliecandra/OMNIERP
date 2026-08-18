import { useEffect, useState } from "react";
import { X, Truck, MapPin, Package, Clock, CheckCircle, XCircle } from "@phosphor-icons/react";
import api from "../lib/api";

const fmt = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(n || 0);

const STATUS_ICON = {
  pending: Clock,
  packed: Package,
  shipped: Truck,
  delivered: CheckCircle,
  cancelled: XCircle,
};

const STATUS_COLOR = {
  pending: "#FFCC00",
  packed: "#007AFF",
  shipped: "#00F2FE",
  delivered: "#34C759",
  cancelled: "#FF3B30",
};

export default function OrderDrawer({ orderId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!orderId) { setDetail(null); return; }
    setLoading(true);
    api.get(`/orders/${orderId}`)
      .then(({ data }) => setDetail(data))
      .finally(() => setLoading(false));
  }, [orderId]);

  const open = Boolean(orderId);

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/70 backdrop-blur-sm transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`}
      />
      {/* Panel */}
      <aside
        data-testid="order-drawer"
        className={`fixed top-0 right-0 z-50 h-screen w-full max-w-xl bg-[#0A0A0A] border-l border-white/10 overflow-y-auto transition-transform duration-200 ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        {open && (
          <>
            <div className="sticky top-0 z-10 bg-[#0A0A0A]/90 backdrop-blur-md border-b border-white/10 px-6 py-4 flex items-start justify-between">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Order Detail</div>
                <h3 className="font-heading text-xl tracking-tight font-bold mt-1 font-mono">
                  {detail?.marketplace_order_id || "…"}
                </h3>
              </div>
              <button data-testid="order-drawer-close" onClick={onClose} className="text-zinc-500 hover:text-white">
                <X size={18} />
              </button>
            </div>

            {loading && (
              <div className="p-8 text-zinc-500 font-mono text-xs uppercase tracking-widest">Loading…</div>
            )}

            {detail && !loading && (
              <div className="p-6 space-y-6">
                {/* Summary tiles */}
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { k: "Revenue", v: fmt(detail.total_revenue) },
                    { k: "COGS",    v: fmt(detail.total_cogs), muted: true },
                    { k: "Profit",  v: fmt(detail.total_revenue - detail.total_cogs), success: true },
                  ].map((t) => (
                    <div key={t.k} className="border border-white/10 p-3">
                      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">{t.k}</div>
                      <div className={`font-mono text-sm mt-1 ${t.success ? "text-[#34C759]" : t.muted ? "text-zinc-400" : "text-white"}`}>{t.v}</div>
                    </div>
                  ))}
                </div>

                {/* Buyer + tracking */}
                <div className="border border-white/10 p-4">
                  <div className="flex items-start gap-2">
                    <MapPin size={16} className="text-zinc-500 mt-0.5" />
                    <div>
                      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Ship to</div>
                      <div className="font-semibold mt-1">{detail.buyer_name || "—"}</div>
                      <div className="text-sm text-zinc-400 mt-0.5">{detail.buyer_address || "Address not provided"}</div>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-white/10 flex items-start gap-2">
                    <Truck size={16} className="text-zinc-500 mt-0.5" />
                    <div>
                      <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Tracking</div>
                      <div className="font-mono text-sm mt-1" data-testid="order-tracking">
                        {detail.tracking_number || "— not assigned —"}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Line items */}
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Line items</div>
                  <div className="border border-white/10" data-testid="order-items">
                    {detail.items.length === 0 && (
                      <div className="p-4 text-zinc-500 text-sm">No items</div>
                    )}
                    {detail.items.map((it, i) => (
                      <div key={i} className={`flex items-center justify-between p-3 ${i < detail.items.length - 1 ? "border-b border-white/5" : ""}`}>
                        <div>
                          <div className="font-mono text-xs text-white">{it.master_sku_code}</div>
                          <div className="text-xs text-zinc-400 mt-0.5">{it.product_name || ""}</div>
                        </div>
                        <div className="text-right font-mono text-sm">
                          <div>{it.quantity} × {fmt(it.unit_price)}</div>
                          <div className="text-[10px] text-zinc-500 mt-0.5">{fmt(it.quantity * it.unit_price)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Timeline */}
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-3">Status timeline</div>
                  <div className="space-y-3" data-testid="order-timeline">
                    {detail.timeline.map((ev, i) => {
                      const Icon = STATUS_ICON[ev.status] || Clock;
                      const color = STATUS_COLOR[ev.status] || "#A1A1AA";
                      return (
                        <div key={i} className="flex items-start gap-3">
                          <div
                            className="w-8 h-8 shrink-0 rounded-sm flex items-center justify-center border"
                            style={{ background: `${color}1a`, borderColor: `${color}55`, color }}
                          >
                            <Icon size={16} weight="duotone" />
                          </div>
                          <div>
                            <div className="text-sm font-semibold capitalize">{ev.status}</div>
                            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mt-0.5">
                              {new Date(ev.at).toISOString().replace("T", " ").slice(0, 16)} UTC
                            </div>
                            {ev.note && <div className="text-xs text-zinc-400 mt-1">{ev.note}</div>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </aside>
    </>
  );
}
