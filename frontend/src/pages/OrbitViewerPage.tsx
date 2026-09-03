import { useState, useMemo } from "react";
import {
  Globe2,
  Sun,
  Camera,
  Layers,
  RotateCcw,
  Zap,
  FastForward,
  Crosshair,
  Activity,
  X,
  MapPin,
  Gauge,
  RefreshCw,
  Compass,
} from "lucide-react";

import { CesiumGlobe, type LiveTelemetry, type ImageryStyle } from "@/components/orbit/CesiumGlobe";
import { SatelliteTrackList } from "@/components/orbit/SatelliteTrackList";
import { useSatellites } from "@/hooks/useSatellites";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

export function OrbitViewerPage() {
  const [fleetScope, setFleetScope] = useState<"mine" | "all">("all");
  const { session } = useAuth();
  const {
    satellites,
    isLoading,
    isSyncing,
    secondsUntilNextSync,
    instantSync,
  } = useSatellites(fleetScope);

  const [focusedId, setFocusedId] = useState<string | null>(null);

  // Orbital View Feature Controls
  const [showAllOrbits, setShowAllOrbits] = useState(true);
  const [showFootprint, setShowFootprint] = useState(true);
  const [autoRotate, setAutoRotate] = useState(true);
  const [enableLighting, setEnableLighting] = useState(false);
  const [enableBloom, setEnableBloom] = useState(false);
  const [followSatellite, setFollowSatellite] = useState(false);
  const [simSpeed, setSimSpeed] = useState<number>(5);
  const [imageryStyle, setImageryStyle] = useState<ImageryStyle>("satellite");

  // Real-time telemetry state for focused object
  const [liveTelemetry, setLiveTelemetry] = useState<LiveTelemetry | null>(null);
  const [isWsConnected, setIsWsConnected] = useState(false);

  // Focused satellite object
  const focusedSatellite = useMemo(() => {
    return satellites.find((s) => s.id === focusedId) || null;
  }, [satellites, focusedId]);

  const authToken = session?.access_token || null;

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Header & Status Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              Orbit Viewer & Space Situational Awareness
            </h1>
            <span className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-[10px] font-mono font-medium text-cyan-400 border border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]">
              3D DIGITAL TWIN
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Sub-satellite propagation, 3D trajectory ribbons, ground tracks, and real-time coverage footprints.
          </p>
        </div>

        {/* Sync & Telemetry Badges */}
        <div className="flex items-center gap-2">
          {/* 10s Sync Engine Status Badge */}
          <div className="flex items-center gap-2 rounded-full border border-border/80 bg-card/70 px-3 py-1 shadow-sm backdrop-blur-md">
            <span className="relative flex h-2 w-2">
              <span
                className={cn(
                  "absolute inline-flex h-full w-full rounded-full opacity-75",
                  isSyncing
                    ? "animate-ping bg-amber-400"
                    : "animate-pulse bg-cyan-400"
                )}
              />
              <span
                className={cn(
                  "relative inline-flex h-2 w-2 rounded-full",
                  isSyncing ? "bg-amber-400" : "bg-cyan-400"
                )}
              />
            </span>
            <span className="text-[11px] font-mono text-muted-foreground">
              {isSyncing ? (
                <span className="text-amber-400 font-semibold">Updating operations...</span>
              ) : (
                <span>10s Sync: <strong className="text-cyan-400">{secondsUntilNextSync}s</strong></span>
              )}
            </span>
            <button
              onClick={() => instantSync()}
              title="Trigger Instant Operation Output"
              className="ml-1 rounded p-0.5 text-muted-foreground hover:bg-secondary hover:text-cyan-300 transition-colors"
            >
              <RefreshCw className={cn("h-3 w-3", isSyncing && "animate-spin text-amber-400")} />
            </button>
          </div>

          {/* Telemetry Protocol Indicator */}
          <div className="flex items-center gap-2 rounded-full border border-border/80 bg-card/70 px-3 py-1 shadow-sm backdrop-blur-md">
            <span className="relative flex h-2 w-2">
              <span
                className={cn(
                  "absolute inline-flex h-full w-full rounded-full opacity-75",
                  isWsConnected ? "animate-ping bg-emerald-400" : "bg-cyan-400"
                )}
              />
              <span
                className={cn(
                  "relative inline-flex h-2 w-2 rounded-full",
                  isWsConnected ? "bg-emerald-400" : "bg-cyan-400"
                )}
              />
            </span>
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
              {isWsConnected ? "WS Live Stream" : "SGP4 IAU Propagator"}
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Track List + 3D Cesium Viewport */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-4">
        {/* Left Side: Fleet List with Filters & Search */}
        <div className="h-[280px] lg:col-span-1 lg:h-full">
          <SatelliteTrackList
            satellites={satellites}
            isLoading={isLoading}
            focusedId={focusedId}
            onFocus={(id) => {
              setFocusedId(id === focusedId ? null : id);
              if (id !== focusedId) setFollowSatellite(false);
            }}
          />
        </div>

        {/* Right Side: 3D Mission Control Cesium Globe */}
        <div className="relative min-h-[440px] flex-1 overflow-hidden rounded-xl border border-border/80 shadow-2xl lg:col-span-3">
          {/* Top Mission Control Floating Toolbar (Orbit View Bar) */}
          <div className="absolute left-3 right-3 top-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
            {/* View / Toggle Buttons */}
            <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border/70 bg-card/85 p-1 shadow-xl backdrop-blur-md pointer-events-auto">
              {/* Fleet Scope Selector */}
              <div className="flex items-center rounded-md bg-secondary/60 p-0.5 border border-border/50">
                <button
                  onClick={() => setFleetScope("all")}
                  title="View All Tracked Objects"
                  className={cn(
                    "rounded px-2 py-0.5 text-xs font-medium transition-all",
                    fleetScope === "all"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Global ({satellites.length})
                </button>
                <button
                  onClick={() => setFleetScope("mine")}
                  title="Filter to My Satellites"
                  className={cn(
                    "rounded px-2 py-0.5 text-xs font-medium transition-all",
                    fleetScope === "mine"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  My Fleet
                </button>
              </div>

              {/* Auto Rotate */}
              <button
                onClick={() => setAutoRotate(!autoRotate)}
                title="Continuous Earth Rotation"
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                  autoRotate
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Globe2 className={cn("h-3.5 w-3.5", autoRotate && "animate-spin text-cyan-400")} />
                <span>Auto-Spin</span>
              </button>

              {/* 3D Orbit Trajectories */}
              <button
                onClick={() => setShowAllOrbits(!showAllOrbits)}
                title="Toggle 3D Orbit Trajectory Ribbons (Instant)"
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                  showAllOrbits
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Zap className="h-3.5 w-3.5" />
                <span>Orbit Paths</span>
              </button>

              {/* Sensor Footprint */}
              <button
                onClick={() => setShowFootprint(!showFootprint)}
                title="Toggle Ground Coverage Footprint"
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                  showFootprint
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Crosshair className="h-3.5 w-3.5" />
                <span>Footprint</span>
              </button>

              {/* Sun / Day-Night Lighting */}
              <button
                onClick={() => setEnableLighting(!enableLighting)}
                title="Toggle Sun Lighting & Day/Night Terminator"
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                  enableLighting
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Sun className="h-3.5 w-3.5" />
                <span>Sun Light</span>
              </button>

              {/* Chaser Camera Follow Mode */}
              {focusedId && (
                <button
                  onClick={() => setFollowSatellite(!followSatellite)}
                  title="Lock Camera & Follow Satellite in Orbit"
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                    followSatellite
                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  <Camera className="h-3.5 w-3.5" />
                  <span>Chaser Cam</span>
                </button>
              )}

              {/* Photorealistic Earth Imagery Presets */}
              <div className="flex items-center gap-0.5 rounded-md bg-secondary/60 p-0.5 border border-border/50">
                <button
                  onClick={() => setImageryStyle("satellite")}
                  title="Photorealistic High-Resolution Satellite Earth (ESRI World Imagery)"
                  className={cn(
                    "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium transition-all",
                    imageryStyle === "satellite"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Globe2 className="h-3 w-3" />
                  <span>Satellite HD</span>
                </button>
                <button
                  onClick={() => setImageryStyle("bluemarble")}
                  title="NASA Blue Marble Next-Gen with Ocean Bathymetry"
                  className={cn(
                    "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium transition-all",
                    imageryStyle === "bluemarble"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Layers className="h-3 w-3" />
                  <span>Blue Marble</span>
                </button>
                <button
                  onClick={() => setImageryStyle("night")}
                  title="NASA Black Marble (Earth at Night / Golden City Lights)"
                  className={cn(
                    "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium transition-all",
                    imageryStyle === "night"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Activity className="h-3 w-3" />
                  <span>City Lights</span>
                </button>
                <button
                  onClick={() => setImageryStyle("dark")}
                  title="Tactical Deep Space Cyber Dark"
                  className={cn(
                    "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium transition-all",
                    imageryStyle === "dark"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <span className="text-[11px] font-mono">Dark</span>
                </button>
              </div>

              {/* HDR Bloom Glow Toggle */}
              <button
                onClick={() => setEnableBloom(!enableBloom)}
                title="Toggle Cinematic HDR Space Bloom Glow"
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                  enableBloom
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <Zap className="h-3.5 w-3.5" />
                <span>HDR Glow</span>
              </button>
            </div>

            {/* Time Warp / Simulation Speed Selector */}
            <div className="flex items-center gap-1 rounded-lg border border-border/70 bg-card/85 p-1 shadow-xl backdrop-blur-md pointer-events-auto">
              <span className="px-2 text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1">
                <FastForward className="h-3 w-3 text-cyan-400" /> Warp:
              </span>
              {[1, 5, 15, 60].map((speed) => (
                <button
                  key={speed}
                  onClick={() => setSimSpeed(speed)}
                  className={cn(
                    "rounded px-2 py-0.5 text-xs font-mono font-medium transition-colors",
                    simSpeed === speed
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  {speed}x
                </button>
              ))}
            </div>
          </div>

          {/* 3D Cesium WebGL Canvas */}
          <CesiumGlobe
            satellites={satellites}
            focusedId={focusedId}
            onSelect={(id) => {
              setFocusedId(id);
              if (!id) setFollowSatellite(false);
            }}
            showAllOrbits={showAllOrbits}
            showFootprint={showFootprint}
            autoRotate={autoRotate}
            enableLighting={enableLighting}
            enableBloom={enableBloom}
            followSatellite={followSatellite}
            simSpeed={simSpeed}
            imageryStyle={imageryStyle}
            authToken={authToken}
            onTelemetryUpdate={setLiveTelemetry}
            onWsStatusChange={setIsWsConnected}
          />

          {/* Floating Focused Satellite Telemetry HUD (Bottom-Right) */}
          {focusedSatellite && (
            <div className="absolute bottom-4 right-4 z-20 w-84 rounded-xl border border-cyan-500/40 bg-[#060B14]/92 p-4 shadow-2xl backdrop-blur-md text-foreground">
              <div className="flex items-start justify-between border-b border-border/60 pb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="flex h-2.5 w-2.5 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(0,242,254,0.9)]" />
                    <h3 className="text-sm font-bold tracking-tight text-white">
                      {focusedSatellite.name}
                    </h3>
                  </div>
                  <p className="text-[11px] font-mono text-muted-foreground">
                    NORAD #{focusedSatellite.noradId} • {focusedSatellite.ownerOrg}
                  </p>
                </div>

                <button
                  onClick={() => {
                    setFocusedId(null);
                    setFollowSatellite(false);
                  }}
                  className="rounded-md p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
                  title="Close HUD"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Live telemetry metrics grid */}
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                {/* Altitude */}
                <div className="rounded-lg border border-border/40 bg-secondary/30 p-2">
                  <div className="flex items-center justify-between text-muted-foreground text-[10px]">
                    <span className="flex items-center gap-1">
                      <Gauge className="h-3 w-3 text-cyan-400" />
                      ALTITUDE
                    </span>
                  </div>
                  <p className="mt-0.5 text-base font-mono font-bold text-white">
                    {liveTelemetry?.altitudeKm ?? (focusedSatellite.altitudeKm ? Math.round(focusedSatellite.altitudeKm * 10) / 10 : "--")}{" "}
                    <span className="text-[10px] font-normal text-muted-foreground">km</span>
                  </p>
                </div>

                {/* Velocity */}
                <div className="rounded-lg border border-border/40 bg-secondary/30 p-2">
                  <div className="flex items-center justify-between text-muted-foreground text-[10px]">
                    <span className="flex items-center gap-1">
                      <Activity className="h-3 w-3 text-emerald-400" />
                      VELOCITY
                    </span>
                  </div>
                  <p className="mt-0.5 text-base font-mono font-bold text-white">
                    {liveTelemetry?.velocityKmS ?? focusedSatellite.velocityKmS ?? 7.66}{" "}
                    <span className="text-[10px] font-normal text-muted-foreground">km/s</span>
                  </p>
                </div>

                {/* Sub-Satellite Point */}
                <div className="col-span-2 rounded-lg border border-border/40 bg-secondary/30 p-2">
                  <div className="flex items-center justify-between text-muted-foreground text-[10px]">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3 text-amber-400" />
                      SUB-SATELLITE POSITION (NADIR)
                    </span>
                    <span className="font-mono text-[9px] text-cyan-400 flex items-center gap-1">
                      <Compass className="h-3 w-3" />
                      WGS84 / IAU
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between font-mono text-xs font-semibold text-white">
                    <span>
                      LAT:{" "}
                      {liveTelemetry
                        ? `${liveTelemetry.latitudeDeg > 0 ? "+" : ""}${liveTelemetry.latitudeDeg.toFixed(3)}°`
                        : `${(focusedSatellite.latitudeDeg ?? 0).toFixed(3)}°`}
                    </span>
                    <span>
                      LON:{" "}
                      {liveTelemetry
                        ? `${liveTelemetry.longitudeDeg > 0 ? "+" : ""}${liveTelemetry.longitudeDeg.toFixed(3)}°`
                        : `${(focusedSatellite.longitudeDeg ?? 0).toFixed(3)}°`}
                    </span>
                  </div>
                </div>

                {/* Orbital Period & Inclination */}
                <div className="rounded-lg border border-border/40 bg-secondary/30 p-2">
                  <p className="text-[10px] text-muted-foreground">PERIOD</p>
                  <p className="font-mono font-semibold text-white">
                    {focusedSatellite.periodMinutes ? `${focusedSatellite.periodMinutes.toFixed(1)} min` : "--"}
                  </p>
                </div>

                <div className="rounded-lg border border-border/40 bg-secondary/30 p-2">
                  <p className="text-[10px] text-muted-foreground">INCLINATION</p>
                  <p className="font-mono font-semibold text-white">
                    {focusedSatellite.inclinationDeg ? `${focusedSatellite.inclinationDeg.toFixed(2)}°` : "--"}
                  </p>
                </div>
              </div>

              {/* Status Footer */}
              <div className="mt-3 flex items-center justify-between border-t border-border/50 pt-2 text-[10px]">
                <span className="text-muted-foreground">Operational State:</span>
                <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-semibold text-emerald-300">
                  {focusedSatellite.status.toUpperCase()} (TRACKING)
                </span>
              </div>
            </div>
          )}

          {/* Bottom Control Bar: Reset View & Sync Output Action */}
          <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2">
            <button
              onClick={() => {
                setFocusedId(null);
                setFollowSatellite(false);
              }}
              title="Reset View"
              className="flex items-center gap-1.5 rounded-lg border border-border/70 bg-card/85 px-2.5 py-1.5 text-xs font-medium text-muted-foreground shadow-lg backdrop-blur-md hover:bg-secondary hover:text-foreground transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset Camera</span>
            </button>

            <button
              onClick={() => instantSync()}
              title="Instant Operation Update Output"
              className="flex items-center gap-1.5 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-2.5 py-1.5 text-xs font-medium text-cyan-300 shadow-lg backdrop-blur-md hover:bg-cyan-500/20 transition-colors"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", isSyncing && "animate-spin text-cyan-400")} />
              <span>Instant Output</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
