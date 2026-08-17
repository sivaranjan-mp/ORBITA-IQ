import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

interface Preference {
  key: string;
  label: string;
  description: string;
  defaultChecked: boolean;
}

const PREFERENCES: Preference[] = [
  {
    key: "critical_email",
    label: "Critical conjunction alerts (email)",
    description: "High and critical risk conjunction events for your tracked fleet.",
    defaultChecked: true,
  },
  {
    key: "daily_digest",
    label: "Daily operations digest",
    description: "A summary of fleet status and alert activity, sent each morning UTC.",
    defaultChecked: true,
  },
  {
    key: "tle_updates",
    label: "TLE / OMM update notifications",
    description: "Notify when new orbital elements are ingested from CelesTrak.",
    defaultChecked: false,
  },
  {
    key: "system_status",
    label: "System status changes",
    description: "Sync job failures, service degradations, and maintenance windows.",
    defaultChecked: true,
  },
];

/** Local-only for now — wire onCheckedChange to a PATCH /users/me/preferences call when available. */
export function NotificationSettings() {
  const [state, setState] = useState<Record<string, boolean>>(
    Object.fromEntries(PREFERENCES.map((p) => [p.key, p.defaultChecked]))
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Notifications</CardTitle>
        <CardDescription>Choose which mission events you're notified about.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y divide-border">
        {PREFERENCES.map((pref) => (
          <div key={pref.key} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
            <div>
              <Label htmlFor={pref.key} className="text-sm font-medium">
                {pref.label}
              </Label>
              <p className="text-xs text-muted-foreground">{pref.description}</p>
            </div>
            <Switch
              id={pref.key}
              checked={state[pref.key]}
              onCheckedChange={(checked) => setState((s) => ({ ...s, [pref.key]: checked }))}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
