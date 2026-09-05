import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export function MissionControlLayout() {
  return (
    <div className="flex h-full w-full overflow-hidden bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col h-full min-h-0 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto min-h-0 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
