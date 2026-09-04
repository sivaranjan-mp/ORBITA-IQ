import { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from "react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import {
  computeGMST,
  computeSubSatellitePoint,
  sampleFullOrbit3D,
  samplePastTrail3D,
  sampleForwardTrajectory3D,
  calculateOrbitalVelocityKmS,
  calculateFootprintRadiusMeters,
  sampleGroundTrack,
} from "@/lib/orbitPropagation";
import type { Satellite, SatelliteStatus } from "@/types/satellite";
import { cn } from "@/lib/utils";

if (typeof window !== "undefined") {
  (window as unknown as { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = "/cesium/";
}

// Distinct high-visibility tracking highlight color (Electric Solar Amber/Gold)
const TRACKING_COLOR = Cesium.Color.fromCssColorString("#FFE600");

// High-contrast status color coding
export const STATUS_COLOR: Record<SatelliteStatus, Cesium.Color> = {
  active: Cesium.Color.fromCssColorString("#00F2FE"),   // Electric Neon Cyan for active operational moving satellites
  degraded: Cesium.Color.fromCssColorString("#FB923C"), // Safety Warning Orange for degraded satellites
  inactive: Cesium.Color.fromCssColorString("#94A3B8"), // Cold Steel Slate for inactive / derelict satellites
  decayed: Cesium.Color.fromCssColorString("#EF4444"),  // Danger Crimson Red for dead satellites & space debris
};

// Dedicated identifiable color per active satellite so each moving orbit is visually distinct
export const ACTIVE_SATELLITE_ORBIT_COLORS: Record<string, Cesium.Color> = {
  "sat-25544": Cesium.Color.fromCssColorString("#00F2FE"), // ISS: Electric Cyan
  "sat-20580": Cesium.Color.fromCssColorString("#38BDF8"), // Hubble: Sky Blue
  "sat-44713": Cesium.Color.fromCssColorString("#818CF8"), // Starlink: Electric Indigo
  "sat-48274": Cesium.Color.fromCssColorString("#10B981"), // Tiangong: Emerald Neon
  "sat-24876": Cesium.Color.fromCssColorString("#FBBF24"), // GPS: Solar Amber Gold
  "sat-49260": Cesium.Color.fromCssColorString("#2DD4BF"), // Landsat: Mint Turquoise
  "sat-46984": Cesium.Color.fromCssColorString("#C084FC"), // Sentinel: Bright Violet
};

const ACTIVE_FALLBACK_PALETTE = [
  Cesium.Color.fromCssColorString("#00F2FE"),
  Cesium.Color.fromCssColorString("#38BDF8"),
  Cesium.Color.fromCssColorString("#818CF8"),
  Cesium.Color.fromCssColorString("#10B981"),
  Cesium.Color.fromCssColorString("#FBBF24"),
  Cesium.Color.fromCssColorString("#2DD4BF"),
  Cesium.Color.fromCssColorString("#C084FC"),
  Cesium.Color.fromCssColorString("#34D399"),
];

export function getSatelliteColor(sat: Satellite, isFocused = false): Cesium.Color {
  if (isFocused) return TRACKING_COLOR;
  if (sat.status === "active") {
    return (
      ACTIVE_SATELLITE_ORBIT_COLORS[sat.id] ||
      ACTIVE_FALLBACK_PALETTE[Math.abs(sat.noradId) % ACTIVE_FALLBACK_PALETTE.length]
    );
  }
  return STATUS_COLOR[sat.status] || STATUS_COLOR.active;
}

export function getSatelliteOrbitStyle(
  sat: Satellite,
  isFocused = false
): { color: Cesium.Color; width: number } {
  if (isFocused) {
    return {
      color: TRACKING_COLOR.withAlpha(0.95),
      width: 3.5,
    };
  }
  if (sat.status === "active") {
    const baseColor = getSatelliteColor(sat, false);
    return {
      color: baseColor.withAlpha(0.72),
      width: 1.8,
    };
  }
  if (sat.status === "degraded") {
    return {
      color: STATUS_COLOR.degraded.withAlpha(0.55),
      width: 1.4,
    };
  }
  if (sat.status === "inactive") {
    return {
      color: STATUS_COLOR.inactive.withAlpha(0.28),
      width: 1.0,
    };
  }
  // decayed / dead debris
  return {
    color: STATUS_COLOR.decayed.withAlpha(0.35),
    width: 1.0,
  };
}

export interface LiveTelemetry {
  satelliteId: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
  velocityKmS: number;
}

export type ImageryStyle = "satellite" | "bluemarble" | "night" | "dark";

export interface CesiumGlobeHandle {
  zoomIn: (factor?: number) => void;
  zoomOut: (factor?: number) => void;
  resetCamera: () => void;
  viewFullEarth: () => void;
  viewLeo: () => void;
  viewMeo: () => void;
  viewGeo: () => void;
  viewDeepSpace: () => void;
  setAltitude: (altitudeKm: number) => void;
  getAltitude: () => number;
}

export interface CesiumGlobeProps {
  satellites: Satellite[];
  focusedId: string | null;
  onSelect: (satelliteId: string | null) => void;
  showAllOrbits?: boolean;
  showFootprint?: boolean;
  autoRotate?: boolean;
  enableLighting?: boolean;
  enableBloom?: boolean;
  simSpeed?: number;
  followSatellite?: boolean;
  imageryStyle?: ImageryStyle;
  authToken?: string | null;
  mouseMode?: "orbit" | "zoom";
  onTelemetryUpdate?: (telemetry: LiveTelemetry | null) => void;
  onWsStatusChange?: (connected: boolean) => void;
  onCameraAltitudeChange?: (altitudeKm: number) => void;
}

interface WsOrbitUpdate {
  satelliteId: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
}

function getImageryProvider(style: ImageryStyle): Cesium.ImageryProvider {
  if (style === "satellite") {
    return new Cesium.UrlTemplateImageryProvider({
      url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      maximumLevel: 19,
      credit: "Esri World Imagery",
    });
  }
  if (style === "bluemarble") {
    return new Cesium.UrlTemplateImageryProvider({
      url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
      maximumLevel: 8,
      credit: "NASA GIBS Blue Marble",
    });
  }
  if (style === "night") {
    return new Cesium.UrlTemplateImageryProvider({
      url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_CityLights_2012/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg",
      maximumLevel: 8,
      credit: "NASA Night Lights",
    });
  }
  return new Cesium.UrlTemplateImageryProvider({
    url: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    subdomains: ["a", "b", "c", "d"],
    maximumLevel: 19,
    credit: "CartoDB Dark Matter",
  });
}

export const CesiumGlobe = forwardRef<CesiumGlobeHandle, CesiumGlobeProps>(function CesiumGlobe(
  {
    satellites,
    focusedId,
    onSelect,
    showAllOrbits = true,
    showFootprint = true,
    autoRotate = false,
    enableLighting = false,
    enableBloom = true,
    simSpeed = 1,
    followSatellite = false,
    imageryStyle = "satellite",
    authToken,
    mouseMode = "orbit",
    onTelemetryUpdate,
    onWsStatusChange,
    onCameraAltitudeChange,
  },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);

  const onCameraAltitudeChangeRef = useRef(onCameraAltitudeChange);
  onCameraAltitudeChangeRef.current = onCameraAltitudeChange;
  const lastReportedAltitudeRef = useRef<number>(23500);

  // Expose camera zoom in / out / reset / presets to parent
  useImperativeHandle(ref, () => ({
    zoomIn: (factor = 0.25) => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      const camera = viewer.camera;
      const carto = camera.positionCartographic;
      const height = carto?.height || 23_500_000;
      // Adaptive smooth exponential zoom step
      const zoomStep = Math.max(30_000, Math.min(height * factor, 30_000_000));
      camera.zoomIn(zoomStep);
    },
    zoomOut: (factor = 0.32) => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      const camera = viewer.camera;
      const carto = camera.positionCartographic;
      const height = carto?.height || 23_500_000;
      const zoomStep = Math.max(40_000, Math.min(height * factor, 45_000_000));
      camera.zoomOut(zoomStep);
    },
    resetCamera: () => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      if (isFollowingRef.current) {
        isFollowingRef.current = false;
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
      }
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(0, 15, 23_500_000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-90),
          roll: 0,
        },
        duration: 0.9,
      });
    },
    viewFullEarth: () => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      if (isFollowingRef.current) {
        isFollowingRef.current = false;
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
      }
      // Perfectly frames the whole spherical Earth with cosmic space background
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(15, 10, 24_500_000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-90),
          roll: 0,
        },
        duration: 0.9,
      });
    },
    viewLeo: () => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(0, 15, 2_400_000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-65),
          roll: 0,
        },
        duration: 0.9,
      });
    },
    viewMeo: () => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(0, 15, 20_000_000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-80),
          roll: 0,
        },
        duration: 0.9,
      });
    },
    viewGeo: () => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(0, 10, 48_000_000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-90),
          roll: 0,
        },
        duration: 1.0,
      });
    },
    viewDeepSpace: () => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(0, 10, 95_000_000),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-90),
          roll: 0,
        },
        duration: 1.1,
      });
    },
    setAltitude: (altitudeKm: number) => {
      const viewer = viewerRef.current;
      if (!viewer) return;
      const camera = viewer.camera;
      const carto = camera.positionCartographic;
      const lon = carto ? Cesium.Math.toDegrees(carto.longitude) : 0;
      const lat = carto ? Cesium.Math.toDegrees(carto.latitude) : 15;
      const targetMeters = Math.max(80_000, Math.min(altitudeKm * 1000, 150_000_000));
      camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(lon, lat, targetMeters),
        duration: 0.7,
      });
    },
    getAltitude: () => {
      const viewer = viewerRef.current;
      if (!viewer) return 23_500;
      const carto = viewer.camera.positionCartographic;
      return carto ? Math.round(carto.height / 1000) : 23_500;
    },
  }));

  const satellitesRef = useRef(satellites);
  satellitesRef.current = satellites;

  const simSpeedRef = useRef(simSpeed);
  simSpeedRef.current = simSpeed;

  const autoRotateRef = useRef(autoRotate);
  autoRotateRef.current = autoRotate;

  const followSatelliteRef = useRef(followSatellite);
  followSatelliteRef.current = followSatellite;

  const focusedIdRef = useRef(focusedId);
  focusedIdRef.current = focusedId;

  const isFollowingRef = useRef(false);
  const cachedFocusedPosCartesian = useRef<Cesium.Cartesian3 | null>(null);
  const cachedFocusedGroundCartesian = useRef<Cesium.Cartesian3 | null>(null);
  const cachedNadirPositions = useRef<Cesium.Cartesian3[]>([]);
  const cachedForwardPositions = useRef<Cesium.Cartesian3[]>([]);
  const cachedPastPositions = useRef<Cesium.Cartesian3[]>([]);
  const cachedGroundTrackPositions = useRef<Cesium.Cartesian3[]>([]);
  const lastPolylineGmstRef = useRef<number>(-999);

  // Cleanly release camera transform lock whenever followSatellite or focusedId is turned off
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    if ((!followSatellite || !focusedId) && isFollowingRef.current) {
      isFollowingRef.current = false;
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    }
  }, [followSatellite, focusedId]);

  // Ultra-fast GPU point primitives for all 611 satellites (1 draw call)
  const pointCollectionRef = useRef<Cesium.PointPrimitiveCollection | null>(null);
  const pointsMapRef = useRef<Map<string, Cesium.PointPrimitive>>(new Map());
  const labelCollectionRef = useRef<Cesium.LabelCollection | null>(null);
  const focusedLabelRef = useRef<Cesium.Label | null>(null);

  // High-performance GPU Polyline collection for full 3D orbital trajectory ribbons
  const polylineCollectionRef = useRef<Cesium.PolylineCollection | null>(null);
  const polylinesMapRef = useRef<Map<string, Cesium.Polyline>>(new Map());

  // Track virtual simulated time offset (milliseconds)
  const simTimeOffsetMsRef = useRef<number>(0);
  const lastRealTimeRef = useRef<number>(Date.now());

  // Store real-time positions pushed from backend WS
  const livePositionsRef = useRef<Record<string, { lat: number; lon: number; alt: number }>>({});
  const [, setWsConnected] = useState(false);

  // Helper to get current simulation date
  const getSimulatedDate = useCallback((): Date => {
    return new Date(Date.now() + simTimeOffsetMsRef.current);
  }, []);

  // 1. Authenticated WebSocket connection to backend
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connectWs = () => {
      try {
        const apiBase =
          import.meta.env.VITE_API_BASE_URL ||
          import.meta.env.VITE_API_URL ||
          "http://localhost:8000/api/v1";

        const wsBase = apiBase.replace(/^http/, "ws").replace(/\/$/, "");

        const token =
          authToken ||
          (() => {
            try {
              const sessionRaw =
                localStorage.getItem("sb-bf2e83d0-auth-token") ||
                localStorage.getItem("supabase.auth.token");
              if (sessionRaw) {
                const parsed = JSON.parse(sessionRaw);
                return parsed?.currentSession?.access_token || parsed?.access_token || null;
              }
            } catch {
              /* ignore */
            }
            return null;
          })();

        const wsUrl = token
          ? `${wsBase}/orbit/ws?token=${encodeURIComponent(token)}`
          : `${wsBase}/orbit/ws`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setWsConnected(true);
          onWsStatusChange?.(true);
        };

        ws.onmessage = (event) => {
          try {
            const data: WsOrbitUpdate = JSON.parse(event.data);
            if (data.satelliteId && data.latitudeDeg != null && data.longitudeDeg != null) {
              livePositionsRef.current[data.satelliteId] = {
                lat: data.latitudeDeg,
                lon: data.longitudeDeg,
                alt: (data.altitudeKm || 500) * 1000,
              };
            }
          } catch {
            /* ignore malformed frames */
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          onWsStatusChange?.(false);
          reconnectTimeout = setTimeout(connectWs, 3000);
        };

        ws.onerror = () => {
          setWsConnected(false);
          onWsStatusChange?.(false);
        };
      } catch {
        setWsConnected(false);
        onWsStatusChange?.(false);
      }
    };

    connectWs();

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws) {
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
      }
    };
  }, [authToken, onWsStatusChange]);

  // 2. Initialize Cesium Viewer with Guaranteed Base Layer and GPU Primitive Pipelines
  useEffect(() => {
    if (!containerRef.current) return;

    Cesium.Ion.defaultAccessToken =
      import.meta.env.VITE_CESIUM_ION_TOKEN ||
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI5NmViZGJjMS05N2Q3LTRlMTEtODNlMy05N2I2YWMyOGI1MDQiLCJpZCI6OTYxMzAsImlhdCI6MTY1NzY0MTU1N30.NImGHf1V8K8mT7MQXR6BN5sI5vmlCMTlHGnHdvFLVpM";

    // Guaranteed local offline NaturalEarthII base layer so Earth always renders on frame 0
    const viewer = new Cesium.Viewer(containerRef.current, {
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      shouldAnimate: true,
      orderIndependentTranslucency: true,
      baseLayer: Cesium.ImageryLayer.fromProviderAsync(
        Cesium.TileMapServiceImageryProvider.fromUrl(
          Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")
        ),
        {}
      ),
      contextOptions: {
        webgl: {
          alpha: false,
          preserveDrawingBuffer: true,
          powerPreference: "high-performance",
        },
      },
    });

    if (viewer.cesiumWidget.creditContainer) {
      (viewer.cesiumWidget.creditContainer as HTMLElement).style.display = "none";
    }

    viewer.resolutionScale = 1.0;
    viewer.useBrowserRecommendedResolution = true;
    viewer.targetFrameRate = 60;
    viewer.scene.globe.maximumScreenSpaceError = 2.5;
    viewer.scene.globe.tileCacheSize = 1000;
    viewer.scene.globe.preloadAncestors = false;
    viewer.scene.globe.depthTestAgainstTerrain = false;

    const scene = viewer.scene;
    // Continuous 60fps WebGL rendering
    scene.requestRenderMode = false;

    // Oceanic blue base so Earth is immediately visible and recognizable
    scene.globe.baseColor = Cesium.Color.fromCssColorString("#0C2340");
    scene.backgroundColor = Cesium.Color.fromCssColorString("#010204");
    scene.globe.enableLighting = enableLighting;

    try {
      scene.skyBox = new Cesium.SkyBox({
        sources: {
          positiveX: Cesium.buildModuleUrl("Assets/Textures/SkyBox/tycho2t3_80_px.jpg"),
          negativeX: Cesium.buildModuleUrl("Assets/Textures/SkyBox/tycho2t3_80_mx.jpg"),
          positiveY: Cesium.buildModuleUrl("Assets/Textures/SkyBox/tycho2t3_80_py.jpg"),
          negativeY: Cesium.buildModuleUrl("Assets/Textures/SkyBox/tycho2t3_80_my.jpg"),
          positiveZ: Cesium.buildModuleUrl("Assets/Textures/SkyBox/tycho2t3_80_pz.jpg"),
          negativeZ: Cesium.buildModuleUrl("Assets/Textures/SkyBox/tycho2t3_80_mz.jpg"),
        },
      });
      scene.skyBox.show = true;
    } catch {
      if (scene.skyBox) scene.skyBox.show = true;
    }

    scene.globe.showGroundAtmosphere = true;
    scene.globe.atmosphereLightIntensity = 10.0;
    scene.globe.atmosphereRayleighScaleHeight = 8500.0;
    scene.globe.atmosphereMieScaleHeight = 1200.0;

    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.atmosphereLightIntensity = 10.0;
      scene.skyAtmosphere.saturationShift = 0.3;
      scene.skyAtmosphere.brightnessShift = 0.15;
      scene.skyAtmosphere.hueShift = -0.02;
    }

    if (scene.sun) scene.sun.show = true;
    if (scene.moon) scene.moon.show = true;

    try {
      if (scene.postProcessStages) {
        if (scene.postProcessStages.bloom) {
          scene.postProcessStages.bloom.enabled = enableBloom;
          scene.postProcessStages.bloom.uniforms.contrast = 110.0;
          scene.postProcessStages.bloom.uniforms.brightness = -0.15;
          scene.postProcessStages.bloom.uniforms.glowOnly = false;
          scene.postProcessStages.bloom.uniforms.delta = 0.9;
          scene.postProcessStages.bloom.uniforms.sigma = 3.5;
          scene.postProcessStages.bloom.uniforms.stepSize = 1.0;
        }
      }
    } catch {
      /* ignore */
    }

    // High-performance GPU Primitive Collections
    const pointCollection = new Cesium.PointPrimitiveCollection();
    scene.primitives.add(pointCollection);
    pointCollectionRef.current = pointCollection;

    const polylineCollection = new Cesium.PolylineCollection();
    scene.primitives.add(polylineCollection);
    polylineCollectionRef.current = polylineCollection;

    const labelCollection = new Cesium.LabelCollection();
    scene.primitives.add(labelCollection);
    labelCollectionRef.current = labelCollection;

    // Camera zoom boundaries: 50 km to 160,000 km (enables close inspection & magnificent Full Earth view)
    scene.screenSpaceCameraController.minimumZoomDistance = 50_000;
    scene.screenSpaceCameraController.maximumZoomDistance = 160_000_000;
    scene.screenSpaceCameraController.enableCollisionDetection = true;
    scene.screenSpaceCameraController.inertiaZoom = 0.68;
    scene.screenSpaceCameraController.inertiaSpin = 0.70;
    scene.screenSpaceCameraController.inertiaTranslate = 0.70;
    scene.screenSpaceCameraController.zoomFactor = 4.0;
    scene.camera.frustum.near = 100.0;

    // Multi-input mouse movement zoom configuration
    scene.screenSpaceCameraController.zoomEventTypes = [
      Cesium.CameraEventType.RIGHT_DRAG,
      Cesium.CameraEventType.WHEEL,
      Cesium.CameraEventType.PINCH,
      Cesium.CameraEventType.MIDDLE_DRAG,
      {
        eventType: Cesium.CameraEventType.LEFT_DRAG,
        modifier: Cesium.KeyboardEventModifier.SHIFT,
      },
      {
        eventType: Cesium.CameraEventType.LEFT_DRAG,
        modifier: Cesium.KeyboardEventModifier.CTRL,
      },
    ];

    // Prevent browser context menu on container so right-drag mouse movement zoom never gets interrupted
    const handleContextMenu = (e: MouseEvent) => e.preventDefault();
    const containerEl = containerRef.current;
    if (containerEl) {
      containerEl.addEventListener("contextmenu", handleContextMenu);
    }

    // Initial camera view over Earth
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(20, 15, 23_500_000),
      orientation: {
        heading: 0,
        pitch: Cesium.Math.toRadians(-90),
        roll: 0,
      },
    });

    // Left-click object picking handler
    const entityHandler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
    entityHandler.setInputAction((movement: { position: Cesium.Cartesian2 }) => {
      const pickedObject = scene.pick(movement.position);
      if (pickedObject && pickedObject.id) {
        const pickedId = typeof pickedObject.id === "string" ? pickedObject.id : pickedObject.id.id;
        const satId = pickedId.replace("-marker", "").replace("-pulse", "").replace("-orbit-path", "").replace("focused-", "");
        const sat = satellitesRef.current.find((s) => s.id === satId);
        if (sat) {
          onSelect(sat.id);
          return;
        }
      }
      if (!pickedObject) {
        onSelect(null);
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    let frameCount = 0;
    // Optimized 60fps Frame Tick Loop: Focused satellite runs at 60fps, background fleet throttled to 10Hz
    const removeTickListener = viewer.clock.onTick.addEventListener(() => {
      frameCount++;
      const now = Date.now();
      const deltaMs = now - lastRealTimeRef.current;
      lastRealTimeRef.current = now;

      if (simSpeedRef.current > 1) {
        simTimeOffsetMsRef.current += deltaMs * (simSpeedRef.current - 1);
      }

      // Background Earth auto-rotation (only when not following satellite)
      if (autoRotateRef.current && !followSatelliteRef.current) {
        scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, 0.0010);
      }

      const simDate = new Date(Date.now() + simTimeOffsetMsRef.current);
      const gmstDeg = computeGMST(simDate);

      // 1. FAST 60FPS UPDATE FOR FOCUSED SATELLITE (Silky-smooth camera & reticle tracking)
      if (focusedIdRef.current) {
        const sat = satellitesRef.current.find((s) => s.id === focusedIdRef.current);
        if (sat) {
          const sub = computeSubSatellitePoint(sat, simDate, gmstDeg);
          if (sub) {
            const satPos = Cesium.Cartesian3.fromDegrees(sub.longitudeDeg, sub.latitudeDeg, sub.heightMeters);
            const groundPos = Cesium.Cartesian3.fromDegrees(sub.longitudeDeg, sub.latitudeDeg, 50);
            cachedFocusedPosCartesian.current = satPos;
            cachedFocusedGroundCartesian.current = groundPos;
            cachedNadirPositions.current = [satPos, groundPos];

            // Point Primitive position update
            const p = pointsMapRef.current.get(sat.id);
            if (p) p.position = satPos;

            // Label position update
            if (focusedLabelRef.current) {
              focusedLabelRef.current.position = satPos;
            }

            // Update forward trajectory & past trail dynamically with satellite motion
            if (frameCount % 3 === 0) {
              const fwd = sampleForwardTrajectory3D(sat, simDate, 95, 60);
              if (fwd.length >= 2) {
                cachedForwardPositions.current = fwd.map((pt) =>
                  Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, pt.heightMeters)
                );
              }
              const past = samplePastTrail3D(sat, simDate, 45, 36);
              if (past.length >= 2) {
                cachedPastPositions.current = past.map((pt) =>
                  Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, pt.heightMeters)
                );
              }
            }

            // Update ground track on Earth surface
            if (frameCount % 18 === 0) {
              const gtrack = sampleGroundTrack(sat, simDate, 50);
              if (gtrack.length >= 2) {
                cachedGroundTrackPositions.current = gtrack.map((pt) =>
                  Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, 500)
                );
              }
            }

            // Camera follow mode
            if (followSatelliteRef.current) {
              const carto = viewer.camera.positionCartographic;
              const altKm = carto ? Math.round(carto.height / 1000) : 1000;
              // If user zooms out to Full Earth view (>20,000 km), cleanly release follow lock
              if (altKm > 20000 && isFollowingRef.current) {
                isFollowingRef.current = false;
                viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
              } else {
                const range = Math.max(1_100_000, sub.heightMeters * 2.0);
                if (!isFollowingRef.current) {
                  isFollowingRef.current = true;
                  scene.camera.lookAt(
                    satPos,
                    new Cesium.HeadingPitchRange(
                      Cesium.Math.toRadians(45),
                      Cesium.Math.toRadians(-28),
                      range
                    )
                  );
                } else {
                  const transform = Cesium.Transforms.eastNorthUpToFixedFrame(satPos);
                  scene.camera.lookAtTransform(transform);
                }
              }
            }
          }
        }
      } else if (isFollowingRef.current) {
        isFollowingRef.current = false;
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
      }

      // 2. BACKGROUND SATELLITE FLEET (Throttled to 10 Hz ~ every 6 frames)
      // Eliminates 85% of CPU math, preventing frame drops and lag!
      if (frameCount % 6 === 0) {
        const pointsMap = pointsMapRef.current;
        const focusedId = focusedIdRef.current;
        satellitesRef.current.forEach((sat) => {
          if (sat.id === focusedId) return; // already updated at 60fps above
          const p = pointsMap.get(sat.id);
          if (!p) return;
          const live = livePositionsRef.current[sat.id];
          if (live) {
            p.position = Cesium.Cartesian3.fromDegrees(live.lon, live.lat, live.alt);
          } else {
            const sub = computeSubSatellitePoint(sat, simDate, gmstDeg);
            if (sub) {
              p.position = Cesium.Cartesian3.fromDegrees(sub.longitudeDeg, sub.latitudeDeg, sub.heightMeters);
            }
          }
        });
      }

      // 3. Synchronize fleet 3D orbit polylines with Earth's sidereal rotation
      // Keeps all 3D orbit ribbons strictly aligned with satellites across all warp speeds (1x, 5x, 15x, 60x)
      if (
        polylinesMapRef.current.size > 0 &&
        Math.abs(gmstDeg - lastPolylineGmstRef.current) >= 0.25
      ) {
        lastPolylineGmstRef.current = gmstDeg;
        const polylinesMap = polylinesMapRef.current;
        const focusedId = focusedIdRef.current;
        satellitesRef.current.forEach((sat) => {
          const polyline = polylinesMap.get(sat.id);
          if (polyline) {
            const isFocused = sat.id === focusedId;
            const pts = sampleFullOrbit3D(sat, simDate, isFocused ? 72 : 48);
            if (pts.length >= 3) {
              polyline.positions = pts.map((p) =>
                Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
              );
            }
          }
        });
      }

      // 3. Throttled camera altitude reporting (every 12 frames ~ 200ms)
      if (frameCount % 12 === 0 && onCameraAltitudeChangeRef.current) {
        const carto = viewer.camera.positionCartographic;
        if (carto) {
          const altKm = Math.round(carto.height / 1000);
          if (altKm !== lastReportedAltitudeRef.current) {
            lastReportedAltitudeRef.current = altKm;
            onCameraAltitudeChangeRef.current(altKm);
          }
        }
      }
    });

    // Resize observer to handle dynamic dashboard flex/grid container resizing
    const resizeObserver = new ResizeObserver(() => {
      viewer.resize();
    });
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    viewerRef.current = viewer;

    const pointsMap = pointsMapRef.current;
    const polylinesMap = polylinesMapRef.current;

    return () => {
      if (containerEl) {
        containerEl.removeEventListener("contextmenu", handleContextMenu);
      }
      resizeObserver.disconnect();
      removeTickListener();
      entityHandler.destroy();
      scene.primitives.remove(pointCollection);
      scene.primitives.remove(polylineCollection);
      scene.primitives.remove(labelCollection);
      viewer.destroy();
      viewerRef.current = null;
      pointCollectionRef.current = null;
      polylineCollectionRef.current = null;
      labelCollectionRef.current = null;
      pointsMap.clear();
      polylinesMap.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Dynamically update camera controls based on active mouseMode ("orbit" vs "zoom")
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const controller = viewer.scene.screenSpaceCameraController;

    if (mouseMode === "zoom") {
      // Direct left-drag mouse movement zoom mode (drag up/down to zoom in/out)
      controller.zoomEventTypes = [
        Cesium.CameraEventType.LEFT_DRAG,
        Cesium.CameraEventType.RIGHT_DRAG,
        Cesium.CameraEventType.WHEEL,
        Cesium.CameraEventType.PINCH,
        Cesium.CameraEventType.MIDDLE_DRAG,
      ];
      controller.rotateEventTypes = [];
    } else {
      // Standard Orbit Navigation: Left-drag rotates, Right/Wheel/Middle/Shift drag zooms
      controller.rotateEventTypes = Cesium.CameraEventType.LEFT_DRAG;
      controller.zoomEventTypes = [
        Cesium.CameraEventType.RIGHT_DRAG,
        Cesium.CameraEventType.WHEEL,
        Cesium.CameraEventType.PINCH,
        Cesium.CameraEventType.MIDDLE_DRAG,
        {
          eventType: Cesium.CameraEventType.LEFT_DRAG,
          modifier: Cesium.KeyboardEventModifier.SHIFT,
        },
        {
          eventType: Cesium.CameraEventType.LEFT_DRAG,
          modifier: Cesium.KeyboardEventModifier.CTRL,
        },
      ];
    }
  }, [mouseMode]);

  // 3. High-Resolution Earth Imagery Layer Management
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    try {
      const provider = getImageryProvider(imageryStyle);
      const layers = viewer.imageryLayers;

      // Add high-resolution overlay
      const overlayLayer = layers.addImageryProvider(provider);
      overlayLayer.alpha = 1.0;

      // Ensure base NaturalEarthII remains if remote tiles are loading or fail
      while (layers.length > 2) {
        layers.remove(layers.get(1));
      }
    } catch {
      /* fallback to offline baseLayer */
    }
  }, [imageryStyle]);

  // 4. Update lighting dynamically
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer?.scene?.globe) {
      viewer.scene.globe.enableLighting = enableLighting;
    }
  }, [enableLighting]);

  // 5. Update HDR space bloom dynamically
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer?.scene?.postProcessStages?.bloom) {
      viewer.scene.postProcessStages.bloom.enabled = enableBloom;
    }
  }, [enableBloom]);

  // 6. High-Performance GPU Satellite Synchronization
  // Renders all 611 satellites in <5ms via a single instanced PointPrimitiveCollection
  useEffect(() => {
    const pointCollection = pointCollectionRef.current;
    if (!pointCollection) return;

    const pointsMap = pointsMapRef.current;
    const currentIds = new Set(satellites.map((s) => s.id));
    const simDate = getSimulatedDate();

    // Remove points no longer in fleet
    for (const [id, pt] of pointsMap.entries()) {
      if (!currentIds.has(id)) {
        pointCollection.remove(pt);
        pointsMap.delete(id);
      }
    }

    // Add or update points for all 611 satellites
    satellites.forEach((sat) => {
      const isFocused = sat.id === focusedIdRef.current;
      const pointColor = getSatelliteColor(sat, isFocused);
      const pt = computeSubSatellitePoint(sat, simDate);
      if (!pt) return;

      const position = Cesium.Cartesian3.fromDegrees(
        pt.longitudeDeg,
        pt.latitudeDeg,
        pt.heightMeters
      );

      const isMovingActive = sat.status === "active";
      const pixelSize = isFocused ? 18 : isMovingActive ? 9 : 6;
      const outlineColor = isFocused
        ? Cesium.Color.WHITE
        : isMovingActive
        ? Cesium.Color.fromCssColorString("#003B46")
        : Cesium.Color.fromCssColorString("#060B14");
      const outlineWidth = isFocused ? 3.5 : isMovingActive ? 2.0 : 1.2;

      const existing = pointsMap.get(sat.id);
      if (existing) {
        existing.position = position;
        existing.pixelSize = pixelSize;
        existing.color = pointColor;
        existing.outlineColor = outlineColor;
        existing.outlineWidth = outlineWidth;
      } else {
        const point = pointCollection.add({
          position,
          pixelSize,
          color: pointColor,
          outlineColor,
          outlineWidth,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          id: sat.id,
        });
        pointsMap.set(sat.id, point);
      }
    });
  }, [satellites, getSimulatedDate]);

  // 7. Render 3D Orbital Trajectories for Fleet (Active Moving Orbits Rendered in Front with Distinct Colors)
  useEffect(() => {
    const polylineCollection = polylineCollectionRef.current;
    if (!polylineCollection) return;

    const polylinesMap = polylinesMapRef.current;
    const simDate = getSimulatedDate();

    // Clear all existing polylines
    polylineCollection.removeAll();
    polylinesMap.clear();

    if (!showAllOrbits && !focusedId) return;

    // Determine which satellites to render orbit paths for
    const satellitesToRender = showAllOrbits
      ? satellites
      : satellites.filter((s) => s.id === focusedId);

    // Sort so inactive/decayed are drawn first in background, and active moving satellites are drawn in front
    const sortedToRender = [...satellitesToRender].sort((a, b) => {
      const rank: Record<SatelliteStatus, number> = {
        inactive: 1,
        decayed: 2,
        degraded: 3,
        active: 4, // drawn last = rendered on top in front!
      };
      return (rank[a.status] || 0) - (rank[b.status] || 0);
    });

    sortedToRender.forEach((sat) => {
      const isFocused = sat.id === focusedId;
      const orbitPoints = sampleFullOrbit3D(sat, simDate, isFocused ? 72 : 48);
      if (orbitPoints.length < 3) return;

      const positions = orbitPoints.map((p) =>
        Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
      );

      const style = getSatelliteOrbitStyle(sat, isFocused);

      const polyline = polylineCollection.add({
        positions,
        width: style.width,
        material: Cesium.Material.fromType("Color", {
          color: style.color,
        }),
      });

      polylinesMap.set(sat.id, polyline);
    });
  }, [satellites, showAllOrbits, focusedId, getSimulatedDate]);

  // 8. Instant Focus Selection Styling: Movement Tracking, Forward Trajectory & Distinct Tracking Color
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Update point colors in PointPrimitiveCollection (highlight tracked satellite in distinct TRACKING_COLOR)
    const pointsMap = pointsMapRef.current;
    for (const [id, pt] of pointsMap.entries()) {
      const isFocused = id === focusedId;
      const sat = satellitesRef.current.find((s) => s.id === id);
      const isMovingActive = sat ? sat.status === "active" : false;
      pt.pixelSize = isFocused ? 18 : isMovingActive ? 9 : 6;
      pt.color = sat ? getSatelliteColor(sat, isFocused) : isFocused ? TRACKING_COLOR : STATUS_COLOR.active;
      pt.outlineColor = isFocused
        ? Cesium.Color.WHITE
        : isMovingActive
        ? Cesium.Color.fromCssColorString("#003B46")
        : Cesium.Color.fromCssColorString("#060B14");
      pt.outlineWidth = isFocused ? 3.5 : isMovingActive ? 2.0 : 1.2;
    }

    // Clean up previous focus entities (ground track, footprint, forward path, past trail, nadir beam, pulse ring)
    const focusSpecific = viewer.entities.values.filter((e) =>
      e.id.startsWith("focused-")
    );
    focusSpecific.forEach((e) => viewer.entities.remove(e));

    // Update label
    if (focusedLabelRef.current && labelCollectionRef.current) {
      labelCollectionRef.current.remove(focusedLabelRef.current);
      focusedLabelRef.current = null;
    }

    const focused = satellitesRef.current.find((s) => s.id === focusedId);
    if (!focused) {
      onTelemetryUpdate?.(null);
      return;
    }

    const simDate = getSimulatedDate();
    const pt = computeSubSatellitePoint(focused, simDate);
    if (!pt) return;

    const focusedPos = Cesium.Cartesian3.fromDegrees(
      pt.longitudeDeg,
      pt.latitudeDeg,
      pt.heightMeters
    );

    // 1. Animated Radar Beacon Pulse Ring around the tracked satellite
    viewer.entities.add({
      id: "focused-pulse-ring",
      position: new Cesium.CallbackPositionProperty(() => {
        return cachedFocusedPosCartesian.current || focusedPos;
      }, false),
      point: {
        pixelSize: new Cesium.CallbackProperty(() => {
          const t = (Date.now() % 1200) / 1200;
          return 16 + t * 20;
        }, false),
        color: new Cesium.CallbackProperty(() => {
          const t = (Date.now() % 1200) / 1200;
          return TRACKING_COLOR.withAlpha(0.85 * (1 - t));
        }, false),
        outlineColor: Cesium.Color.WHITE.withAlpha(0.5),
        outlineWidth: 1.5,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });

    // 2. Forward 3D Trajectory Ribbon ("Where it is going next")
    const forwardPoints = sampleForwardTrajectory3D(focused, simDate, 95, 60);
    if (forwardPoints.length > 2) {
      cachedForwardPositions.current = forwardPoints.map((p) =>
        Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
      );
      viewer.entities.add({
        id: "focused-forward-path",
        polyline: {
          positions: new Cesium.CallbackProperty(() => cachedForwardPositions.current, false),
          width: 3.5,
          material: new Cesium.PolylineGlowMaterialProperty({
            glowPower: 0.25,
            taperPower: 0.85,
            color: TRACKING_COLOR,
          }),
        },
      });
    }

    // 3. Past 3D Trajectory Trail ("Where it just was")
    const pastPoints = samplePastTrail3D(focused, simDate, 45, 36);
    if (pastPoints.length > 2) {
      cachedPastPositions.current = pastPoints.map((p) =>
        Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
      );
      viewer.entities.add({
        id: "focused-past-trail",
        polyline: {
          positions: new Cesium.CallbackProperty(() => cachedPastPositions.current, false),
          width: 2.0,
          material: new Cesium.PolylineDashMaterialProperty({
            color: TRACKING_COLOR.withAlpha(0.45),
            dashLength: 12.0,
          }),
        },
      });
    }

    // 4. Sub-satellite Nadir Altitude Beam (connecting satellite in space to its ground coordinate)
    viewer.entities.add({
      id: "focused-nadir-beam",
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          return cachedNadirPositions.current.length > 0
            ? cachedNadirPositions.current
            : [focusedPos, Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, 0)];
        }, false),
        width: 2.0,
        material: new Cesium.PolylineDashMaterialProperty({
          color: TRACKING_COLOR.withAlpha(0.8),
          dashLength: 8.0,
        }),
      },
    });

    // 5. Sub-satellite Ground Target Disc
    viewer.entities.add({
      id: "focused-ground-target",
      position: new Cesium.CallbackPositionProperty(() => {
        return cachedFocusedGroundCartesian.current || Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, 50);
      }, false),
      point: {
        pixelSize: 8,
        color: TRACKING_COLOR,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
      },
    });

    // 6. Label for focused satellite with [TRACKING] badge in TRACKING_COLOR
    if (labelCollectionRef.current) {
      focusedLabelRef.current = labelCollectionRef.current.add({
        position: focusedPos,
        text: `● ${focused.name} [TRACKING]`,
        font: "bold 13px 'Inter', sans-serif",
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        fillColor: TRACKING_COLOR,
        outlineColor: Cesium.Color.fromCssColorString("#060B14"),
        outlineWidth: 3,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -20),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      });
    }

    // 7. Nadir Ground Footprint Disk in matching Tracking Color
    if (showFootprint) {
      const footprintRadius = calculateFootprintRadiusMeters(focused);
      viewer.entities.add({
        id: "focused-footprint",
        position: new Cesium.CallbackPositionProperty(() => {
          return cachedFocusedGroundCartesian.current || Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, 0);
        }, false),
        ellipse: {
          semiMajorAxis: footprintRadius,
          semiMinorAxis: footprintRadius,
          material: TRACKING_COLOR.withAlpha(0.12),
          outline: true,
          outlineColor: TRACKING_COLOR.withAlpha(0.85),
          outlineWidth: 2.0,
          height: 100,
        },
      });
    }

    // 8. Ground Track Line on Earth in Tracking Color
    const groundTrackPoints = sampleGroundTrack(focused, simDate, 50);
    if (groundTrackPoints.length > 2) {
      cachedGroundTrackPositions.current = groundTrackPoints.map((p) =>
        Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, 500)
      );
      viewer.entities.add({
        id: "focused-ground-track",
        polyline: {
          positions: new Cesium.CallbackProperty(() => cachedGroundTrackPositions.current, false),
          width: 2.5,
          material: new Cesium.PolylineDashMaterialProperty({
            color: TRACKING_COLOR.withAlpha(0.9),
            dashLength: 12.0,
          }),
        },
      });
    }

    // 9. Update real-time telemetry callback
    const velocity = calculateOrbitalVelocityKmS(focused);
    onTelemetryUpdate?.({
      satelliteId: focused.id,
      latitudeDeg: pt.latitudeDeg,
      longitudeDeg: pt.longitudeDeg,
      altitudeKm: pt.heightMeters / 1000,
      velocityKmS: velocity,
    });

    // 10. Initial smooth fly-to framing the satellite
    const range = Math.max(3_500_000, pt.heightMeters * 3.0);
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        pt.longitudeDeg,
        pt.latitudeDeg - 8,
        pt.heightMeters + range
      ),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-40),
        roll: 0.0,
      },
      duration: 1.0,
    });
  }, [focusedId, showFootprint, getSimulatedDate, onTelemetryUpdate]);



  return (
    <div
      ref={containerRef}
      className={cn(
        "absolute inset-0 w-full h-full min-h-[450px] overflow-hidden select-none bg-[#010204]",
        mouseMode === "zoom" ? "cursor-ns-resize" : "cursor-grab active:cursor-grabbing"
      )}
    />
  );
});
