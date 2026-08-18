import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Lightning } from "@phosphor-icons/react";
import api from "../lib/api";

export default function Login() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post("/login", { username, password });
      localStorage.setItem("erp_token", data.access_token);
      localStorage.setItem("erp_user", data.username);
      toast.success("Signed in");
      navigate("/dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-[#0A0A0A] text-white relative z-[2]">
      {/* Left panel — brand / stats */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 border-r border-white/10 p-12">
        <div className="flex items-center gap-2">
          <Lightning weight="fill" size={24} className="text-[#007AFF]" />
          <span className="font-heading font-black tracking-tighter uppercase">Omni.ERP</span>
        </div>

        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 mb-4">
            SINGLE SOURCE OF TRUTH
          </div>
          <h1 className="font-heading text-5xl tracking-tighter font-black leading-[0.95]">
            Command every marketplace
            <br />
            <span className="text-[#007AFF]">from one screen.</span>
          </h1>
          <p className="mt-6 text-zinc-400 max-w-md leading-relaxed">
            Unified inventory, orders and profitability across Shopee, TikTok Shop and beyond.
            Deduct stock in real-time via marketplace webhooks.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-6 border-t border-white/10 pt-8">
          {[
            { k: "STORES", v: "4+" },
            { k: "PLATFORMS", v: "2" },
            { k: "LATENCY", v: "<80ms" },
          ].map((s) => (
            <div key={s.k}>
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-500">{s.k}</div>
              <div className="font-heading font-black text-2xl tracking-tight mt-1">{s.v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <form
          onSubmit={submit}
          data-testid="login-form"
          className="w-full max-w-sm border border-white/10 bg-[#0A0A0A] p-8 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-500 mb-2">
            SECURE ACCESS · JWT
          </div>
          <h2 className="font-heading text-3xl tracking-tight font-bold mb-8">Sign in</h2>

          <label className="block text-xs font-mono uppercase tracking-widest text-zinc-500 mb-2">Username</label>
          <input
            data-testid="login-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] focus:ring-1 focus:ring-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm mb-5 rounded-sm"
            autoComplete="username"
            required
          />

          <label className="block text-xs font-mono uppercase tracking-widest text-zinc-500 mb-2">Password</label>
          <input
            data-testid="login-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-transparent border border-white/20 focus:border-[#007AFF] focus:ring-1 focus:ring-[#007AFF] outline-none px-3 py-2 text-white font-mono text-sm mb-8 rounded-sm"
            autoComplete="current-password"
            required
          />

          <button
            data-testid="login-submit"
            type="submit"
            disabled={loading}
            className="w-full bg-[#007AFF] hover:bg-[#0056B3] text-white font-semibold py-2.5 rounded-sm text-sm uppercase tracking-wider transition-colors disabled:opacity-60"
          >
            {loading ? "Authenticating…" : "Enter Command Center"}
          </button>

          <div className="mt-6 font-mono text-[10px] uppercase tracking-widest text-zinc-600 text-center">
            Default: admin / admin
          </div>
        </form>
      </div>
    </div>
  );
}
