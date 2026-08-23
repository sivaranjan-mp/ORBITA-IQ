import { NavLink } from "react-router-dom";
import { AlertTriangle, Globe2, LayoutDashboard, Satellite, Settings } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/satellites", label: "My Satellites", icon: Satellite },
  { to: "/all-satellites", label: "All Satellites", icon: Globe2 },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/orbit-viewer", label: "Orbit Viewer", icon: Globe2 },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card/60 md:flex">
      <div className="flex h-16 items-center gap-2.5 border-b border-border px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/15">
          <Satellite className="h-4 w-4 text-primary" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight">MISSION CONTROL</p>
          <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
            Conjunction Intel
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2 rounded-md bg-secondary/50 px-3 py-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          <span className="text-xs font-medium text-muted-foreground">
            All systems nominal
          </span>
        </div>
      </div>
    </aside>
  );
}
