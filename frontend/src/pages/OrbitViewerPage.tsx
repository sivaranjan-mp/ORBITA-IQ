import { useState, useMemo, useRef, useEffect, useCallback } from "react";
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
  PanelLeft,
  PanelLeftClose,
  Minimize2,
  Maximize2,
  ZoomIn,
  ZoomOut,
  Move,
  Search,
  HelpCircle,
  Sliders,
  ChevronUp,
  ChevronDown,
} from "lucide-react";

import {
  CesiumGlobe,
  type CesiumGlobeHandle,
  type LiveTelemetry,
  type ImageryStyle,
} from "@/components/orbit/CesiumGlobe";
import { SatelliteTrackList } from "@/components/orbit/SatelliteTrackList";
import { useSatellites } from "@/hooks/useSatellites";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

export function OrbitViewerPage() {
  const globeRef = useRef<CesiumGlobeHandle>(null);
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
  const [simSpeed, setSimSpeed] = useState<number>(15);
  const [imageryStyle, setImageryStyle] = useState<ImageryStyle>("satellite");

  // Selection Handler: Auto-stop Earth rotation & auto-follow satellite on pick
  const handleSelectSatellite = useCallback((id: string | null) => {
    if (id) {
      setFocusedId(id);
      setAutoRotate(false); // Stop Earth auto-rotation
      setFollowSatellite(true); // Auto-lock camera and follow satellite in orbit
    } else {
      setFocusedId(null);
      setFollowSatellite(false);
    }
  }, []);

  // Mouse & Camera Zoom Navigation Controls
  const [mouseMode, setMouseMode] = useState<"orbit" | "zoom">("orbit");
  const [cameraAltitudeKm, setCameraAltitudeKm] = useState<number>(23500);
  const [showMouseHelp, setShowMouseHelp] = useState(false);
  const zoomIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const moveIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Continuous hold-to-zoom handlers
  const startContinuousZoom = (direction: "in" | "out") => {
    if (direction === "in") {
      globeRef.current?.zoomIn(0.18);
    } else {
      globeRef.current?.zoomOut(0.24);
    }

    if (zoomIntervalRef.current) clearInterval(zoomIntervalRef.current);
    zoomIntervalRef.current = setInterval(() => {
      if (direction === "in") {
        globeRef.current?.zoomIn(0.12);
      } else {
        globeRef.current?.zoomOut(0.16);
      }
    }, 70);
  };

  const stopContinuousZoom = () => {
    if (zoomIntervalRef.current) {
      clearInterval(zoomIntervalRef.current);
      zoomIntervalRef.current = null;
    }
  };

  // Continuous hold-to-move handlers (Up / Down)
  const startContinuousMove = (direction: "up" | "down") => {
    if (direction === "up") {
      globeRef.current?.moveUp(4);
    } else {
      globeRef.current?.moveDown(4);
    }

    if (moveIntervalRef.current) clearInterval(moveIntervalRef.current);
    moveIntervalRef.current = setInterval(() => {
      if (direction === "up") {
        globeRef.current?.moveUp(3);
      } else {
        globeRef.current?.moveDown(3);
      }
    }, 60);
  };

  const stopContinuousMove = () => {
    if (moveIntervalRef.current) {
      clearInterval(moveIntervalRef.current);
      moveIntervalRef.current = null;
    }
  };

  // Global Keyboard Shortcuts for Zoom & Movement (+ / - / ArrowUp / ArrowDown / C / 0)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target as HTMLElement).isContentEditable
      ) {
        return;
      }

      if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        globeRef.current?.zoomIn(0.25);
      } else if (e.key === "-" || e.key === "_") {
        e.preventDefault();
        globeRef.current?.zoomOut(0.35);
      } else if (e.key === "ArrowUp" || e.key === "w" || e.key === "W") {
        e.preventDefault();
        globeRef.current?.moveUp(5);
      } else if (e.key === "ArrowDown" || e.key === "s" || e.key === "S") {
        e.preventDefault();
        globeRef.current?.moveDown(5);
      } else if (e.key === "c" || e.key === "C") {
        e.preventDefault();
        globeRef.current?.centerEarth();
      } else if (e.key === "0" || e.key === "f" || e.key === "F") {
        e.preventDefault();
        handleSelectSatellite(null);
        globeRef.current?.viewFullEarth();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (zoomIntervalRef.current) clearInterval(zoomIntervalRef.current);
      if (moveIntervalRef.current) clearInterval(moveIntervalRef.current);
    };
  }, [handleSelectSatellite]);

  // Orbit Shell metadata based on live camera altitude
  const shellInfo = useMemo(() => {
    if (cameraAltitudeKm < 2000) {
      return {
        shell: "LEO",
        label: "Low Earth Orbit",
        color: "text-emerald-400 bg-emerald-500/15 border-emerald-500/35",
      };
    }
    if (cameraAltitudeKm < 30000) {
      return {
        shell: "MEO",
        label: "Medium Earth (GPS/Nav)",
        color: "text-cyan-400 bg-cyan-500/15 border-cyan-500/35",
      };
    }
    if (cameraAltitudeKm < 50000) {
      return {
        shell: "GEO",
        label: "Geostationary Belt",
        color: "text-amber-400 bg-amber-500/15 border-amber-500/35",
      };
    }
    return {
      shell: "DEEP",
      label: "Deep Space Volume",
      color: "text-purple-400 bg-purple-500/15 border-purple-500/35",
    };
  }, [cameraAltitudeKm]);

  // Logarithmic slider mapping [0..100] <=> [300km..100000km]
  const currentSliderVal = useMemo(() => {
    const clamped = Math.max(300, Math.min(cameraAltitudeKm, 100000));
    return Math.round((Math.log(clamped / 300) / Math.log(100000 / 300)) * 100);
  }, [cameraAltitudeKm]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    const targetAltKm = Math.round(300 * Math.pow(100000 / 300, val / 100));
    setCameraAltitudeKm(targetAltKm);
    globeRef.current?.setAltitude(targetAltKm);
  };

  // Real-time telemetry state for focused object
  const [liveTelemetry, setLiveTelemetry] = useState<LiveTelemetry | null>(null);
  const [isWsConnected, setIsWsConnected] = useState(false);

  // Layout Controls
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isHudMinimized, setIsHudMinimized] = useState(false);

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

      {/* Main Grid: Track List + 3D Cesium Viewport (Full Horizontal Widescreen Support) */}
      <div className="flex min-h-0 flex-1 gap-3 overflow-hidden">
        {/* Left Side: Fleet List with Filters & Search (Collapsible) */}
        {isSidebarOpen && (
          <div className="w-80 shrink-0 h-full transition-all duration-300">
            <SatelliteTrackList
              satellites={satellites}
              isLoading={isLoading}
              focusedId={focusedId}
              onFocus={(id) => {
                if (!id || id === focusedId) {
                  handleSelectSatellite(null);
                } else {
                  handleSelectSatellite(id);
                }
              }}
            />
          </div>
        )}

        {/* Right Side / Full Width: 3D Mission Control Cesium Globe */}
        <div className="relative min-h-[440px] flex-1 overflow-hidden rounded-xl border border-border/80 shadow-2xl">
          {/* Top Mission Control Floating Toolbar (Orbit View Bar) */}
          <div className="absolute left-3 right-3 top-3 z-10 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
            {/* View / Toggle Buttons */}
            <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border/70 bg-card/85 p-1 shadow-xl backdrop-blur-md pointer-events-auto">
              {/* Full Horizontal View Toggle Button */}
              <button
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                title={isSidebarOpen ? "Maximize Horizontal Space View" : "Show Fleet Panel"}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                  !isSidebarOpen
                    ? "bg-cyan-500/25 text-cyan-300 border border-cyan-500/40 shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                {isSidebarOpen ? <PanelLeftClose className="h-3.5 w-3.5" /> : <PanelLeft className="h-3.5 w-3.5" />}
                <span>{isSidebarOpen ? "Wide View" : "Show Fleet"}</span>
              </button>

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

              {/* Mouse Movement Mode: Rotate vs Drag Zoom */}
              <div className="flex items-center rounded-md bg-secondary/60 p-0.5 border border-border/50">
                <button
                  onClick={() => setMouseMode("orbit")}
                  title="Orbit Mode: Left-drag rotates Earth, Wheel & Right-drag zooms"
                  className={cn(
                    "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium transition-all",
                    mouseMode === "orbit"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Move className="h-3 w-3" />
                  <span>Rotate</span>
                </button>
                <button
                  onClick={() => setMouseMode("zoom")}
                  title="Mouse Drag Zoom Mode: Click and drag mouse up/down anywhere on globe to zoom"
                  className={cn(
                    "flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium transition-all",
                    mouseMode === "zoom"
                      ? "bg-cyan-500/25 text-cyan-300 font-semibold shadow-sm border border-cyan-500/40 animate-pulse"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Search className="h-3 w-3" />
                  <span>Drag Zoom</span>
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
                  title={followSatellite ? "Camera locked to satellite orbit (Click to unlock)" : "Lock Camera & Follow Satellite in Orbit"}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all",
                    followSatellite
                      ? "bg-amber-500/25 text-amber-300 border border-amber-500/50 shadow-[0_0_12px_rgba(255,230,0,0.25)]"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  <Camera className={cn("h-3.5 w-3.5", followSatellite && "text-amber-300 animate-pulse")} />
                  <span>{followSatellite ? "Following Orbit" : "Follow Cam"}</span>
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

            {/* Time Warp / Simulation Speed Selector (1x and 5x removed) */}
            <div className="flex items-center gap-1 rounded-lg border border-border/70 bg-card/85 p-1 shadow-xl backdrop-blur-md pointer-events-auto">
              <span className="px-2 text-[10px] font-mono uppercase text-muted-foreground flex items-center gap-1">
                <FastForward className="h-3 w-3 text-cyan-400" /> Warp:
              </span>
              {[15, 30, 60, 120].map((speed) => (
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

          {/* Mouse Drag Zoom Active Notification Banner (Top Center) */}
          {mouseMode === "zoom" && (
            <div className="absolute top-16 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2.5 rounded-full border border-cyan-500/50 bg-[#060B14]/92 px-4 py-1.5 shadow-[0_0_20px_rgba(6,182,212,0.3)] backdrop-blur-md pointer-events-auto animate-in fade-in slide-in-from-top-2 duration-200">
              <Search className="h-3.5 w-3.5 text-cyan-400 animate-pulse" />
              <span className="text-xs font-medium text-cyan-200">
                Mouse Drag Zoom Active: <strong className="text-white">Drag up to zoom in, down to zoom out</strong>
              </span>
              <button
                onClick={() => setMouseMode("orbit")}
                className="ml-2 rounded-full border border-cyan-500/40 bg-cyan-500/20 px-2.5 py-0.5 text-[10px] font-semibold text-cyan-300 hover:bg-cyan-500/35 transition-colors"
              >
                Back to Rotate
              </button>
            </div>
          )}

          {/* Floating Right Navigation & Movement Dock */}
          <div className="absolute right-3 top-16 z-20 flex flex-col items-center gap-1.5 rounded-xl border border-border/80 bg-[#060B14]/90 p-1.5 shadow-2xl backdrop-blur-md pointer-events-auto">
            {/* Move Up Button (Click or Hold) */}
            <button
              onMouseDown={() => startContinuousMove("up")}
              onMouseUp={stopContinuousMove}
              onMouseLeave={stopContinuousMove}
              onTouchStart={() => startContinuousMove("up")}
              onTouchEnd={stopContinuousMove}
              onClick={() => globeRef.current?.moveUp(6)}
              title="Move View Up (Click or Hold / Shortcut: ArrowUp or W)"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/60 text-foreground hover:bg-cyan-500/25 hover:text-cyan-300 transition-all active:scale-95 border border-border/40"
            >
              <ChevronUp className="h-4 w-4" />
            </button>

            {/* Center Earth Button */}
            <button
              onClick={() => {
                handleSelectSatellite(null);
                globeRef.current?.centerEarth();
              }}
              title="Center Earth in View (Shortcut: C)"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/30 hover:text-cyan-200 transition-all active:scale-95 border border-cyan-500/35 shadow-[0_0_10px_rgba(6,182,212,0.25)]"
            >
              <Crosshair className="h-4 w-4" />
            </button>

            {/* Move Down Button (Click or Hold) */}
            <button
              onMouseDown={() => startContinuousMove("down")}
              onMouseUp={stopContinuousMove}
              onMouseLeave={stopContinuousMove}
              onTouchStart={() => startContinuousMove("down")}
              onTouchEnd={stopContinuousMove}
              onClick={() => globeRef.current?.moveDown(6)}
              title="Move View Down (Click or Hold / Shortcut: ArrowDown or S)"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/60 text-foreground hover:bg-cyan-500/25 hover:text-cyan-300 transition-all active:scale-95 border border-border/40"
            >
              <ChevronDown className="h-4 w-4" />
            </button>

            <div className="h-[1px] w-6 bg-border/60 my-0.5" />

            {/* Zoom In (+) with continuous hold */}
            <button
              onMouseDown={() => startContinuousZoom("in")}
              onMouseUp={stopContinuousZoom}
              onMouseLeave={stopContinuousZoom}
              onTouchStart={() => startContinuousZoom("in")}
              onTouchEnd={stopContinuousZoom}
              onClick={() => globeRef.current?.zoomIn()}
              title="Zoom In Closer (Click or Hold / Shortcut: +)"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/60 text-foreground hover:bg-cyan-500/25 hover:text-cyan-300 transition-all active:scale-95 border border-border/40"
            >
              <ZoomIn className="h-4 w-4" />
            </button>

            {/* Vertical Altitude Slider */}
            <div className="flex flex-col items-center py-1 group relative">
              <input
                type="range"
                min="0"
                max="100"
                value={currentSliderVal}
                onChange={handleSliderChange}
                aria-label="Orbit Altitude Zoom Slider"
                title={`Altitude: ${cameraAltitudeKm.toLocaleString()} km (${shellInfo.shell})`}
                className="h-20 w-1.5 accent-cyan-400 bg-secondary/80 rounded-lg cursor-pointer [appearance:slider-vertical]"
              />
            </div>

            {/* Zoom Out (-) with continuous hold */}
            <button
              onMouseDown={() => startContinuousZoom("out")}
              onMouseUp={stopContinuousZoom}
              onMouseLeave={stopContinuousZoom}
              onTouchStart={() => startContinuousZoom("out")}
              onTouchEnd={stopContinuousZoom}
              onClick={() => globeRef.current?.zoomOut()}
              title="Zoom Out Farther (Click or Hold / Shortcut: -)"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/60 text-foreground hover:bg-cyan-500/25 hover:text-cyan-300 transition-all active:scale-95 border border-border/40"
            >
              <ZoomOut className="h-4 w-4" />
            </button>

            <div className="h-[1px] w-6 bg-border/60 my-0.5" />

            {/* Full Earth View Button */}
            <button
              onClick={() => {
                handleSelectSatellite(null);
                globeRef.current?.viewFullEarth();
              }}
              title="Full Earth View (Whole Earth in Space / Shortcut: F or 0)"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-cyan-400 hover:bg-cyan-500/20 hover:text-cyan-300 transition-all active:scale-95"
            >
              <Globe2 className="h-4 w-4" />
            </button>

            {/* Reset View */}
            <button
              onClick={() => {
                handleSelectSatellite(null);
                globeRef.current?.resetCamera();
              }}
              title="Reset Earth View (Shortcut: 0)"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-secondary/70 hover:text-foreground transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>

            {/* Mouse Mode Quick Toggle */}
            <button
              onClick={() => setMouseMode(mouseMode === "orbit" ? "zoom" : "orbit")}
              title={mouseMode === "zoom" ? "Switch to Orbit / Rotate Mode" : "Switch to Mouse Drag Zoom Mode"}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-lg transition-all",
                mouseMode === "zoom"
                  ? "bg-cyan-500/30 text-cyan-300 border border-cyan-500/50 shadow-[0_0_10px_rgba(6,182,212,0.25)] animate-pulse"
                  : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground"
              )}
            >
              {mouseMode === "zoom" ? <Search className="h-3.5 w-3.5" /> : <Move className="h-3.5 w-3.5" />}
            </button>

            {/* Controls Guide Button */}
            <button
              onClick={() => setShowMouseHelp(!showMouseHelp)}
              title="Navigation & Controls Guide"
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                showMouseHelp
                  ? "bg-cyan-500/25 text-cyan-300"
                  : "text-muted-foreground hover:bg-secondary/70 hover:text-foreground"
              )}
            >
              <HelpCircle className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Navigation & Controls Help Guide Modal / Flyout */}
          {showMouseHelp && (
            <div className="absolute right-14 top-16 z-30 w-76 rounded-xl border border-cyan-500/40 bg-[#060B14]/95 p-3.5 shadow-2xl backdrop-blur-md text-foreground animate-in fade-in slide-in-from-right-2 duration-150">
              <div className="flex items-center justify-between border-b border-border/60 pb-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                  <Compass className="h-3.5 w-3.5 text-cyan-400" />
                  <span>Orbit Navigation & Controls</span>
                </div>
                <button
                  onClick={() => setShowMouseHelp(false)}
                  className="rounded p-1 text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="mt-2.5 space-y-2 text-[11px] text-muted-foreground">
                <div className="flex items-start gap-2">
                  <span className="font-mono text-cyan-400 font-bold shrink-0">1.</span>
                  <div>
                    <strong className="text-white">Move Up & Down:</strong> Click or hold the <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">▲</kbd> / <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">▼</kbd> buttons, or press <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">↑</kbd> / <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">↓</kbd> or <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">W</kbd> / <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">S</kbd> to move the view up and down over Earth.
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="font-mono text-cyan-400 font-bold shrink-0">2.</span>
                  <div>
                    <strong className="text-white">Center Earth:</strong> Click the target crosshair button or press <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">C</kbd> to lock Earth back to the exact center of the screen.
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="font-mono text-cyan-400 font-bold shrink-0">3.</span>
                  <div>
                    <strong className="text-white">Mouse Scroll Wheel:</strong> Scroll forward to zoom in, backward to zoom out directly towards the cursor.
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="font-mono text-cyan-400 font-bold shrink-0">4.</span>
                  <div>
                    <strong className="text-white">Right-Click Drag:</strong> Hold right mouse button and move mouse up to zoom in, down to zoom out.
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="font-mono text-cyan-400 font-bold shrink-0">5.</span>
                  <div>
                    <strong className="text-white">Drag Zoom Mode:</strong> Switch to Drag Zoom tool to zoom in/out with standard left-click drag anywhere.
                  </div>
                </div>
                <div className="flex items-start gap-2 border-t border-border/40 pt-1.5">
                  <span className="font-mono text-cyan-400 font-bold shrink-0">6.</span>
                  <div>
                    <strong className="text-white">Keyboard Shortcuts:</strong> <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">+</kbd> Zoom in, <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">-</kbd> Zoom out, <kbd className="rounded bg-secondary/80 px-1 py-0.5 text-[10px] font-mono text-white border border-border/50">0</kbd> Reset view.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 3D Cesium WebGL Canvas */}
          <CesiumGlobe
            ref={globeRef}
            satellites={satellites}
            focusedId={focusedId}
            onSelect={(id) => {
              if (!id || id === focusedId) {
                handleSelectSatellite(null);
              } else {
                handleSelectSatellite(id);
              }
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
            mouseMode={mouseMode}
            onTelemetryUpdate={setLiveTelemetry}
            onWsStatusChange={setIsWsConnected}
            onCameraAltitudeChange={setCameraAltitudeKm}
          />

          {/* Floating Focused Satellite Telemetry HUD (Bottom-Right, Compact & Minimizable) */}
          {focusedSatellite && (
            isHudMinimized ? (
              <div className="absolute bottom-3 right-3 z-20 flex items-center gap-2.5 rounded-xl border border-amber-400/50 bg-[#060B14]/92 px-3 py-2 shadow-[0_0_20px_rgba(255,230,0,0.2)] backdrop-blur-md text-foreground">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75 animate-ping" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#FFE600] shadow-[0_0_8px_rgba(255,230,0,0.9)]" />
                </span>
                <span className="text-xs font-bold text-white">{focusedSatellite.name}</span>
                <span className="rounded bg-amber-400/20 px-1.5 py-0.5 text-[9px] font-mono font-bold text-amber-300 border border-amber-400/30">
                  TRACKING
                </span>
                <span className="font-mono text-[11px] text-amber-300 font-semibold">
                  {liveTelemetry?.altitudeKm ? `${Math.round(liveTelemetry.altitudeKm)} km` : `${focusedSatellite.altitudeKm ? Math.round(focusedSatellite.altitudeKm) : "--"} km`}
                </span>
                <button
                  onClick={() => setIsHudMinimized(false)}
                  className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-amber-300 transition-colors"
                  title="Expand Telemetry HUD"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => handleSelectSatellite(null)}
                  className="rounded p-1 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
                  title="Stop Tracking & Close HUD"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <div className="absolute bottom-3 right-3 z-20 w-80 rounded-xl border border-amber-400/50 bg-[#060B14]/94 p-3.5 shadow-[0_0_25px_rgba(255,230,0,0.25)] backdrop-blur-md text-foreground">
                <div className="flex items-start justify-between border-b border-border/60 pb-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="relative flex h-3 w-3">
                        <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75 animate-ping" />
                        <span className="relative inline-flex h-3 w-3 rounded-full bg-[#FFE600] shadow-[0_0_10px_rgba(255,230,0,0.9)]" />
                      </span>
                      <h3 className="text-sm font-bold tracking-tight text-white">
                        {focusedSatellite.name}
                      </h3>
                      <span className="rounded bg-amber-400/20 px-1.5 py-0.5 text-[9px] font-mono font-bold text-amber-300 border border-amber-400/40">
                        TRACKING
                      </span>
                    </div>
                    <p className="text-[11px] font-mono text-muted-foreground mt-0.5">
                      NORAD #{focusedSatellite.noradId} • {focusedSatellite.ownerOrg}
                    </p>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setIsHudMinimized(true)}
                      className="rounded-md p-1 text-muted-foreground hover:bg-secondary hover:text-amber-300 transition-colors"
                      title="Minimize HUD"
                    >
                      <Minimize2 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => handleSelectSatellite(null)}
                      className="rounded-md p-1 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
                      title="Stop Tracking & Close HUD"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {/* Live telemetry metrics grid */}
                <div className="mt-2.5 grid grid-cols-2 gap-1.5 text-xs">
                  {/* Altitude */}
                  <div className="rounded-lg border border-border/40 bg-secondary/30 p-1.5">
                    <div className="flex items-center justify-between text-muted-foreground text-[10px]">
                      <span className="flex items-center gap-1">
                        <Gauge className="h-3 w-3 text-cyan-400" />
                        ALTITUDE
                      </span>
                    </div>
                    <p className="mt-0.5 text-sm font-mono font-bold text-white">
                      {liveTelemetry?.altitudeKm ?? (focusedSatellite.altitudeKm ? Math.round(focusedSatellite.altitudeKm * 10) / 10 : "--")}{" "}
                      <span className="text-[10px] font-normal text-muted-foreground">km</span>
                    </p>
                  </div>

                  {/* Velocity */}
                  <div className="rounded-lg border border-border/40 bg-secondary/30 p-1.5">
                    <div className="flex items-center justify-between text-muted-foreground text-[10px]">
                      <span className="flex items-center gap-1">
                        <Activity className="h-3 w-3 text-emerald-400" />
                        VELOCITY
                      </span>
                    </div>
                    <p className="mt-0.5 text-sm font-mono font-bold text-white">
                      {liveTelemetry?.velocityKmS ?? focusedSatellite.velocityKmS ?? 7.66}{" "}
                      <span className="text-[10px] font-normal text-muted-foreground">km/s</span>
                    </p>
                  </div>

                  {/* Sub-Satellite Point */}
                  <div className="col-span-2 rounded-lg border border-border/40 bg-secondary/30 p-1.5">
                    <div className="flex items-center justify-between text-muted-foreground text-[10px]">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3 text-amber-400" />
                        SUB-SATELLITE POSITION
                      </span>
                      <span className="font-mono text-[9px] text-cyan-400 flex items-center gap-0.5">
                        <Compass className="h-2.5 w-2.5" />
                        WGS84
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center justify-between font-mono text-[11px] font-semibold text-white">
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
                  <div className="rounded-lg border border-border/40 bg-secondary/30 p-1.5">
                    <p className="text-[9px] text-muted-foreground">PERIOD</p>
                    <p className="font-mono text-xs font-semibold text-white">
                      {focusedSatellite.periodMinutes ? `${focusedSatellite.periodMinutes.toFixed(1)} min` : "--"}
                    </p>
                  </div>

                  <div className="rounded-lg border border-border/40 bg-secondary/30 p-1.5">
                    <p className="text-[9px] text-muted-foreground">INCLINATION</p>
                    <p className="font-mono text-xs font-semibold text-white">
                      {focusedSatellite.inclinationDeg ? `${focusedSatellite.inclinationDeg.toFixed(2)}°` : "--"}
                    </p>
                  </div>
                </div>

                {/* Status Footer */}
                <div className="mt-2 flex items-center justify-between border-t border-border/50 pt-1.5 text-[10px]">
                  <span className="text-muted-foreground">State:</span>
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 font-semibold text-[10px] font-mono",
                      focusedSatellite.status === "active"
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : focusedSatellite.status === "degraded"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : focusedSatellite.status === "inactive"
                        ? "bg-slate-500/20 text-slate-300 border border-slate-500/30"
                        : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                    )}
                  >
                    {focusedSatellite.status === "active" ? "ACTIVE • MOVING" : focusedSatellite.status.toUpperCase()}
                  </span>
                </div>
              </div>
            )
          )}

          {/* Status & Orbit Color Legend Overlay */}
          <div className="absolute bottom-16 left-3 z-10 hidden sm:flex items-center gap-2.5 rounded-lg border border-border/70 bg-[#060B14]/90 px-3 py-1.5 shadow-xl backdrop-blur-md pointer-events-auto text-[11px] font-mono">
            <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Orbits:</span>
            <span className="flex items-center gap-1.5 text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.9)]" />
              Active (Moving)
            </span>
            <span className="flex items-center gap-1.5 text-amber-300">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              Degraded
            </span>
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="h-2 w-2 rounded-full bg-slate-400" />
              Inactive (Derelict)
            </span>
            <span className="flex items-center gap-1.5 text-rose-400">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              Dead (Debris)
            </span>
            <span className="flex items-center gap-1.5 text-amber-200 border-l border-border/60 pl-2">
              <span className="h-2 w-2 rounded-full bg-[#FFE600] shadow-[0_0_8px_rgba(255,230,0,0.9)]" />
              Tracked
            </span>
          </div>

          {/* Bottom Control Bar: Zoom Controls, Altitude HUD, Presets, Slider & Sync Output */}
          <div className="absolute bottom-3 left-3 z-10 flex flex-wrap items-center gap-2 pointer-events-auto">
            {/* Dedicated Zoom In (+) & Zoom Out (-) Controls with Continuous Hold-to-Zoom */}
            <div className="flex items-center rounded-lg border border-border/70 bg-card/85 p-0.5 shadow-lg backdrop-blur-md">
              <button
                onMouseDown={() => startContinuousZoom("in")}
                onMouseUp={stopContinuousZoom}
                onMouseLeave={stopContinuousZoom}
                onTouchStart={() => startContinuousZoom("in")}
                onTouchEnd={stopContinuousZoom}
                onClick={() => globeRef.current?.zoomIn()}
                title="Zoom In Closer (Click or Hold / Shortcut: +)"
                className="flex items-center justify-center rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-cyan-300 transition-colors active:scale-95"
              >
                <ZoomIn className="h-4 w-4" />
              </button>
              <div className="h-4 w-[1px] bg-border/60 mx-0.5" />
              <button
                onMouseDown={() => startContinuousZoom("out")}
                onMouseUp={stopContinuousZoom}
                onMouseLeave={stopContinuousZoom}
                onTouchStart={() => startContinuousZoom("out")}
                onTouchEnd={stopContinuousZoom}
                onClick={() => globeRef.current?.zoomOut()}
                title="Zoom Out Farther (Click or Hold / Shortcut: -)"
                className="flex items-center justify-center rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-cyan-300 transition-colors active:scale-95"
              >
                <ZoomOut className="h-4 w-4" />
              </button>
            </div>

            {/* Live Camera Altitude HUD & Orbital Shell Badge */}
            <div className="flex items-center gap-1.5 rounded-lg border border-border/70 bg-card/85 px-2.5 py-1 shadow-lg backdrop-blur-md">
              <Gauge className="h-3.5 w-3.5 text-cyan-400" />
              <div className="flex items-baseline gap-1.5">
                <span className="text-[10px] font-mono uppercase text-muted-foreground">ALT:</span>
                <span className="font-mono text-xs font-bold text-white">
                  {cameraAltitudeKm.toLocaleString()} <span className="text-[10px] font-normal text-muted-foreground">km</span>
                </span>
                <span
                  title={shellInfo.label}
                  className={cn("rounded border px-1.5 py-0.5 text-[9px] font-mono font-semibold", shellInfo.color)}
                >
                  {shellInfo.shell}
                </span>
              </div>
            </div>

            {/* Quick Horizontal Altitude Slider */}
            <div className="hidden md:flex items-center gap-1.5 rounded-lg border border-border/70 bg-card/85 px-2.5 py-1 shadow-lg backdrop-blur-md">
              <Sliders className="h-3 w-3 text-cyan-400" />
              <input
                type="range"
                min="0"
                max="100"
                value={currentSliderVal}
                onChange={handleSliderChange}
                aria-label="Altitude Zoom Level"
                title={`Drag to zoom: ${cameraAltitudeKm.toLocaleString()} km`}
                className="w-20 accent-cyan-400 cursor-pointer h-1.5 bg-secondary/80 rounded"
              />
            </div>

            {/* Orbit Altitude Presets (Full Earth / LEO / MEO / GEO / Deep / Reset) */}
            <div className="flex items-center rounded-lg border border-border/70 bg-card/85 p-0.5 shadow-lg backdrop-blur-md">
              <button
                onClick={() => {
                  handleSelectSatellite(null);
                  globeRef.current?.viewFullEarth();
                }}
                title="Full Earth Space View (~24,500 km - Whole Earth Centered / Shortcut: F or 0)"
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-cyan-300 bg-cyan-500/15 border border-cyan-500/30 hover:bg-cyan-500/25 transition-colors shadow-sm"
              >
                <Globe2 className="h-3 w-3" />
                <span>Full Earth</span>
              </button>
              <button
                onClick={() => {
                  handleSelectSatellite(null);
                  globeRef.current?.viewLeo();
                }}
                title="Low Earth Orbit Zoom View (2,400 km)"
                className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-emerald-300 transition-colors"
              >
                LEO
              </button>
              <button
                onClick={() => {
                  handleSelectSatellite(null);
                  globeRef.current?.viewMeo();
                }}
                title="Medium Earth Orbit Navigation View (20,000 km)"
                className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-cyan-300 transition-colors"
              >
                MEO
              </button>
              <button
                onClick={() => {
                  handleSelectSatellite(null);
                  globeRef.current?.viewGeo();
                }}
                title="Geostationary Space Zoom View (48,000 km)"
                className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-amber-300 transition-colors"
              >
                GEO
              </button>
              <button
                onClick={() => {
                  handleSelectSatellite(null);
                  globeRef.current?.viewDeepSpace();
                }}
                title="Deep Space Outer Orbit View (95,000 km)"
                className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-purple-300 transition-colors"
              >
                Deep
              </button>
              <button
                onClick={() => {
                  handleSelectSatellite(null);
                  globeRef.current?.resetCamera();
                }}
                title="Reset Camera (Global Space View / Shortcut: 0)"
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Reset</span>
              </button>
            </div>

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
