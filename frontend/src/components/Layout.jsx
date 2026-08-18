import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  ChartLineUp, Package, ShoppingBagOpen, Storefront,
  SignOut, List, X, Lightning,
} from "@phosphor-icons/react";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: ChartLineUp, testid: "nav-dashboard" },
  { to: "/orders",    label: "Order Hub", icon: ShoppingBagOpen, testid: "nav-orders" },
  { to: "/inventory", label: "Inventory", icon: Package, testid: "nav-inventory" },
  { to: "/stores",    label: "Stores",    icon: Storefront, testid: "nav-stores" },
];

export default function Layout() {
  const [open, setOpen] = useState(true);
  const navigate = useNavigate();
  const username = localStorage.getItem("erp_user") || "admin";

  const logout = () => {
    localStorage.removeItem("erp_token");
    localStorage.removeItem("erp_user");
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-[#0A0A0A] text-white relative z-[2]">
      <aside
        data-testid="sidebar"
        className={`${open ? "w-60" : "w-16"} shrink-0 border-r border-white/10 flex flex-col transition-[width] duration-200`}
      >
        <div className="h-16 flex items-center justify-between px-4 border-b border-white/10">
          <div className="flex items-center gap-2 overflow-hidden">
            <Lightning weight="fill" size={20} className="text-[#007AFF] shrink-0" />
            {open && <span className="font-heading font-black tracking-tighter text-sm uppercase whitespace-nowrap">Omni.ERP</span>}
          </div>
          <button
            data-testid="sidebar-toggle"
            onClick={() => setOpen(!open)}
            className="text-zinc-500 hover:text-white p-1"
          >
            {open ? <X size={16} /> : <List size={16} />}
          </button>
        </div>

        <nav className="flex-1 py-4">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                data-testid={item.testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 border-l-2 text-sm hover:bg-white/5 hover:text-white transition-colors ${
                    isActive
                      ? "border-[#007AFF] bg-white/5 text-white"
                      : "border-transparent text-zinc-400"
                  }`
                }
              >
                <Icon size={18} weight="regular" className="shrink-0" />
                {open && <span className="font-medium">{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        <div className="border-t border-white/10 p-3">
          <div className={`flex items-center gap-3 ${open ? "" : "justify-center"}`}>
            <div className="w-8 h-8 rounded-sm bg-[#007AFF]/20 border border-[#007AFF]/40 flex items-center justify-center text-[#007AFF] font-mono text-xs uppercase shrink-0">
              {username.slice(0, 2)}
            </div>
            {open && (
              <div className="flex-1 min-w-0">
                <div className="text-xs font-mono uppercase tracking-widest text-zinc-500">Signed in</div>
                <div className="text-sm text-white truncate">{username}</div>
              </div>
            )}
            <button
              data-testid="logout-btn"
              onClick={logout}
              className="text-zinc-500 hover:text-[#FF3B30] p-1 transition-colors"
              title="Sign out"
            >
              <SignOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}
