import { useState } from "react";

import { CesiumGlobe } from "@/components/orbit/CesiumGlobe";
import { SatelliteTrackList } from "@/components/orbit/SatelliteTrackList";
import { useSatellites } from "@/hooks/useSatellites";

export function OrbitViewerPage() {
  const { satellites, isLoading } = useSatellites();
  const [focusedId, setFocusedId] = useState<string | null>(null);

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Orbit Viewer</h1>
        <p className="text-sm text-muted-foreground">
          Real-time sub-satellite positions and predicted ground track for the selected object.
        </p>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-4">
        <div className="lg:col-span-1">
          <SatelliteTrackList
            satellites={satellites}
            isLoading={isLoading}
            focusedId={focusedId}
            onFocus={(id) => setFocusedId(id === focusedId ? null : id)}
          />
        </div>
        <div className="min-h-[420px] overflow-hidden rounded-lg border border-border lg:col-span-3">
          <CesiumGlobe satellites={satellites} focusedId={focusedId} onSelect={setFocusedId} />
        </div>
      </div>
    </div>
  );
}
