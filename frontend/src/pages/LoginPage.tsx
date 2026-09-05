import { Satellite } from "lucide-react";

import { LoginForm } from "@/components/auth/LoginForm";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function LoginPage() {
  return (
    <div className="flex h-full w-full items-center justify-center overflow-y-auto bg-background px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-border bg-card">
            <Satellite className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Orbita-IQ Console</h1>
            <p className="text-sm text-muted-foreground">Conjunction Intelligence Dashboard</p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Sign in</CardTitle>
            <CardDescription>Use your Employee ID and password to continue.</CardDescription>
          </CardHeader>
          <CardContent>
            <LoginForm />
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Admin and Operator accounts use the same sign-in form — access is
          determined by your assigned role after authentication.
        </p>
      </div>
    </div>
  );
}
