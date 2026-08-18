import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Storefront, CheckCircle, Circle, PencilSimple, X, PlugsConnected, SlackLogo, ArrowsClockwise } from "@phosphor-icons/react";
import api from "../lib/api";

const PLATFORM = {
  shopee: { color: "#FF5722", label: "Shopee" },
  tiktok: { color: "#00F2FE", label: "TikTok Shop" },
};

function CredentialsModal({ open, store, onClose, onSaved }) {
  const [partnerId, setPartnerId] = useState("");
  const [partnerKey, setPartnerKey] = useState("");
  const [shopId, setShopId] = useState("");
  const [syncEnabled, setSyncEnabled] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && store) {
      setPartnerId(store.partner_id || "");
      setPartnerKey("");
      setShopId(store.shop_id || "");
      setSyncEnabled(store.sync_enabled || false);
    }
  }, [open, store]);

  if (!open || !store) return null;

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const body = {
        partner_id: partnerId || null,
        shop_id: shopId || null,
        sync_enabled: syncEnabled,
      };
      if (partnerKey) body.partner_key = partnerKey;
      await api.patch(`/stores/${store.id}`, body);
      toast.success("Store connection updated");
      onSaved();
      onClose();
    } catch {
      toast.error("Failed to update store");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <form onSubmit={submit} data-testid="store-modal" className="w-full max-w-lg bg-[#0A0A0A] border border-white/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Marketplace Connection</div>
            <h3 className="font-heading text-xl tracking-tight font-bold mt-1">{store.store_name}</h3>
          </div>
          <button type="button" data-testid="store-modal-close" onClick={onClose} className="text-zinc-500 hover:text-white"><X size={18} /></button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Partner ID</label>
            <input data-testid="store-partner-id" value={partnerId} onChange={(e) => setPartnerId(e.target.value)}
              placeholder="from Shopee Open Platform"
              className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm rounded-sm" />
          </div>
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">
              Partner Key {store.partner_id && <span className="text-zinc-600 normal-case tracking-normal">(leave blank to keep existing)</span>}
            </label>
            <input data-testid="store-partner-key" type="password" value={partnerKey} onChange={(e) => setPartnerKey(e.target.value)}
              placeholder="••••••••••••••••"
              className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm rounded-sm" />
          </div>
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Shop ID</label>
            <input data-testid="store-shop-id" value={shopId} onChange={(e) => setShopId(e.target.value)}
              className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm rounded-sm" />
          </div>

          <label className="flex items-center gap-3 border border-white/10 p-4 cursor-pointer">
            <input data-testid="store-sync-toggle" type="checkbox" checked={syncEnabled} onChange={(e) => setSyncEnabled(e.target.checked)} className="accent-[#007AFF] w-4 h-4" />
            <div>
              <div className="text-sm font-semibold">Enable auto-sync</div>
              <div className="text-xs text-zinc-500 mt-0.5">Background worker pulls new orders every 5 minutes</div>
            </div>
          </label>

          {store.last_sync_at && (
            <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
              Last sync: {new Date(store.last_sync_at).toISOString().slice(0, 16).replace("T", " ")} · {store.last_sync_status || "—"}
            </div>
          )}
        </div>

        <div className="border-t border-white/10 px-6 py-4 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="border border-white/10 text-white hover:bg-white/5 px-4 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors">Cancel</button>
          <button data-testid="store-modal-submit" type="submit" disabled={saving} className="bg-[#007AFF] hover:bg-[#0056B3] text-white font-semibold px-4 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors disabled:opacity-60">
            {saving ? "Saving…" : "Save Connection"}
          </button>
        </div>
      </form>
    </div>
  );
}

function SlackCard() {
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get("/settings").then(({ data }) => {
      setUrl(data.slack_webhook_url || "");
      setLoaded(true);
    });
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/settings", { slack_webhook_url: url });
      toast.success(url ? "Slack alerts enabled" : "Slack alerts disabled");
    } catch {
      toast.error("Failed to save");
    } finally { setSaving(false); }
  };

  return (
    <div data-testid="slack-card" className="border border-white/10 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 flex items-center justify-center rounded-sm bg-[#4A154B]/30 border border-[#4A154B]/60">
          <SlackLogo size={22} weight="fill" className="text-[#ECB22E]" />
        </div>
        <div>
          <div className="font-heading font-bold text-lg tracking-tight">Slack Alerts</div>
          <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">Low-stock notifications</div>
        </div>
        <span className={`ml-auto text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 border rounded-sm ${url ? "text-[#34C759] border-[#34C759]/40 bg-[#34C759]/10" : "text-zinc-500 border-white/10 bg-white/5"}`}>
          {url ? "ACTIVE" : "OFF"}
        </span>
      </div>

      <label className="block text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-2">Incoming Webhook URL</label>
      <input
        data-testid="slack-webhook-input"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://hooks.slack.com/services/T…/B…/…"
        disabled={!loaded}
        className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] outline-none px-3 py-2 text-white font-mono text-xs rounded-sm"
      />
      <p className="text-xs text-zinc-500 mt-2">Any master SKU that drops to or below its reorder threshold triggers a Slack message.</p>

      <div className="flex justify-end mt-4">
        <button
          data-testid="slack-webhook-save"
          onClick={save} disabled={saving || !loaded}
          className="bg-[#007AFF] hover:bg-[#0056B3] text-white font-semibold px-4 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save Webhook"}
        </button>
      </div>
    </div>
  );
}

export default function Stores() {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/stores");
      setStores(data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  return (
    <div data-testid="stores-page">
      <header className="border-b border-white/10 px-8 py-6">
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">CONNECTIONS</div>
        <h1 className="font-heading text-3xl tracking-tight font-bold mt-1">Stores & Alerts</h1>
      </header>

      <div className="p-8 space-y-8">
        <SlackCard />

        {loading && <div className="text-zinc-500 font-mono text-xs uppercase tracking-widest">Loading…</div>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {stores.map((s) => {
            const p = PLATFORM[s.platform_name] || { color: "#FFFFFF", label: s.platform_name };
            const configured = Boolean(s.partner_id);
            return (
              <div key={s.id} data-testid={`store-card-${s.id}`} className="border border-white/10 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center justify-center rounded-sm"
                      style={{ background: `${p.color}1a`, border: `1px solid ${p.color}55` }}>
                      <Storefront size={20} weight="duotone" style={{ color: p.color }} />
                    </div>
                    <div>
                      <div className="font-heading font-bold text-lg tracking-tight">{s.store_name}</div>
                      <div className="text-[10px] font-mono uppercase tracking-widest" style={{ color: p.color }}>{p.label}</div>
                    </div>
                  </div>
                  <span className={`flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest ${s.is_active ? "text-[#34C759]" : "text-zinc-500"}`}>
                    {s.is_active ? <CheckCircle size={14} weight="fill" /> : <Circle size={14} />}
                    {s.is_active ? "ACTIVE" : "PAUSED"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 font-mono text-xs pt-4 border-t border-white/10 mb-4">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500">Auto-Sync</div>
                    <div className={`mt-1 flex items-center gap-1.5 ${s.sync_enabled ? "text-[#34C759]" : "text-zinc-500"}`}>
                      {s.sync_enabled ? <><ArrowsClockwise size={12} weight="bold" /> ON</> : "OFF"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500">Credentials</div>
                    <div className={`mt-1 flex items-center gap-1.5 ${configured ? "text-white" : "text-zinc-500"}`}>
                      <PlugsConnected size={12} /> {configured ? "connected" : "not set"}
                    </div>
                  </div>
                </div>

                {s.last_sync_at && (
                  <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-3">
                    LAST SYNC · {new Date(s.last_sync_at).toISOString().slice(0, 16).replace("T", " ")} · {s.last_sync_status || "—"}
                  </div>
                )}

                <button
                  data-testid={`store-edit-${s.id}`}
                  onClick={() => setEditing(s)}
                  className="w-full flex items-center justify-center gap-2 border border-white/10 hover:bg-white/5 text-white px-3 py-2 rounded-sm text-xs uppercase tracking-wider transition-colors"
                >
                  <PencilSimple size={14} /> Manage Connection
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <CredentialsModal open={Boolean(editing)} store={editing} onClose={() => setEditing(null)} onSaved={load} />
    </div>
  );
}
