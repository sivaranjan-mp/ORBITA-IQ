import { ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { formatDateTime } from "@/lib/format";

export function ProfileSettings() {
  const { profile, role } = useAuth();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Profile</CardTitle>
        <CardDescription>Identity and role information tied to your account.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Full name</Label>
          <Input value={profile?.full_name ?? ""} disabled />
        </div>
        <div className="space-y-1.5">
          <Label>Employee ID</Label>
          <Input value={profile?.employee_id ?? ""} disabled className="font-mono" />
        </div>
        <div className="space-y-1.5">
          <Label>Department</Label>
          <Input value={profile?.department ?? "—"} disabled />
        </div>
        <div className="space-y-1.5">
          <Label>Role</Label>
          <div className="flex h-10 items-center">
            <Badge variant="default" className="capitalize">
              <ShieldCheck className="h-3 w-3" />
              {role}
            </Badge>
          </div>
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label>Last login</Label>
          <Input
            value={profile?.last_login_at ? formatDateTime(profile.last_login_at) : "—"}
            disabled
          />
        </div>
      </CardContent>
    </Card>
  );
}
