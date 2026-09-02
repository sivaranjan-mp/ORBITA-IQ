import { useState, useEffect, type FormEvent } from "react";
import { Check, Loader2, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { apiClient } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";

export function ProfileSettings() {
  const { profile, role, refreshProfile } = useAuth();
  const [fullName, setFullName] = useState(profile?.full_name ?? "");
  const [department, setDepartment] = useState(profile?.department ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (profile) {
      setFullName(profile.full_name ?? "");
      setDepartment(profile.department ?? "");
    }
  }, [profile]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!fullName.trim()) {
      setErrorMsg("Full name cannot be empty.");
      return;
    }

    setIsSaving(true);
    setErrorMsg(null);
    setSaveSuccess(false);

    try {
      await apiClient.patch("/auth/me", {
        full_name: fullName.trim(),
        department: department.trim() || null,
      });
      await refreshProfile();
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      console.error("Failed to update profile", err);
      setErrorMsg("Failed to update profile. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  const hasChanges =
    fullName.trim() !== (profile?.full_name ?? "") ||
    department.trim() !== (profile?.department ?? "");

  return (
    <Card>
      <form onSubmit={handleSave}>
        <CardHeader>
          <CardTitle className="text-base">Profile</CardTitle>
          <CardDescription>Identity and role information tied to your account.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="full_name">Full name</Label>
            <Input
              id="full_name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Sivaranjan M P"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="employee_id">Employee ID</Label>
            <Input
              id="employee_id"
              value={profile?.employee_id ?? ""}
              disabled
              className="font-mono bg-muted/50 cursor-not-allowed"
            />
            <p className="text-[11px] text-muted-foreground">Managed by system administrator.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="department">Department</Label>
            <Input
              id="department"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="e.g. Flight Operations"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Role</Label>
            <div className="flex h-10 items-center">
              <Badge variant="default" className="capitalize">
                <ShieldCheck className="mr-1 h-3 w-3" />
                {role}
              </Badge>
            </div>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Last login</Label>
            <Input
              value={profile?.last_login_at ? formatDateTime(profile.last_login_at) : "—"}
              disabled
              className="bg-muted/50"
            />
          </div>

          {errorMsg && (
            <div className="sm:col-span-2 text-xs text-destructive font-medium">
              {errorMsg}
            </div>
          )}

          {saveSuccess && (
            <div className="sm:col-span-2 flex items-center gap-1.5 text-xs text-emerald-500 font-medium">
              <Check className="h-3.5 w-3.5" />
              Profile updated successfully!
            </div>
          )}
        </CardContent>
        <CardFooter className="border-t px-6 py-4 flex justify-end">
          <Button type="submit" size="sm" disabled={isSaving || !hasChanges}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Changes
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
