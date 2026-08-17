import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MissionClock } from "@/components/layout/MissionClock";
import { useAuth } from "@/hooks/useAuth";

function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function Topbar() {
  const { profile, role, logout } = useAuth();

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur">
      <div>
        <p className="text-sm font-semibold tracking-tight">Ground Operations</p>
        <p className="text-xs text-muted-foreground">Conjunction Intelligence Dashboard</p>
      </div>

      <div className="flex items-center gap-4">
        <MissionClock />

        <div className="flex items-center gap-3 border-l border-border pl-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
            {profile ? initials(profile.full_name) : "—"}
          </div>
          <div className="hidden leading-tight sm:block">
            <p className="text-sm font-medium">{profile?.full_name ?? "—"}</p>
            <p className="text-xs capitalize text-muted-foreground">
              {role ?? "—"} · {profile?.employee_id ?? "—"}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={() => logout()} title="Log out">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
