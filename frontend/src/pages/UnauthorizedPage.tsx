import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";

export function UnauthorizedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      <ShieldAlert className="h-10 w-10 text-destructive" />
      <div>
        <h1 className="text-lg font-semibold">Access restricted</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your role does not have permission to view this page.
        </p>
      </div>
      <Button asChild variant="secondary">
        <Link to="/dashboard">Back to dashboard</Link>
      </Button>
    </div>
  );
}
