import { useEffect, useRef, useState, useCallback } from "react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import {
  computeSubSatellitePoint,
  sampleFullOrbit3D,
  calculateOrbitalVelocityKmS,
  calculateFootprintRadiusMeters,
  sampleGroundTrack,
} from "@/lib/orbitPropagation";
import type { Satellite, SatelliteStatus } from "@/types/satellite";

const STATUS_COLOR: Record<SatelliteStatus, Cesium.Color> = {
  active: Cesium.Color.fromCssColorString("#00F2FE"),
  degraded: Cesium.Color.fromCssColorString("#F5A623"),
  inactive: Cesium.Color.fromCssColorString("#8B98B3"),
  decayed: Cesium.Color.fromCssColorString("#F2545B"),
};

export interface LiveTelemetry {
  satelliteId: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
  velocityKmS: number;
}

export type ImageryStyle = "satellite" | "bluemarble" | "night" | "dark";

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
  onTelemetryUpdate?: (telemetry: LiveTelemetry | null) => void;
  onWsStatusChange?: (connected: boolean) => void;
}

interface WsOrbitUpdate {
  satelliteId: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
}

interface SatelliteEntityRecord {
  marker: Cesium.Entity;
  orbit?: Cesium.Entity;
  status: SatelliteStatus;
}

export function CesiumGlobe({
  satellites,
  focusedId,
  onSelect,
  showAllOrbits = true,
  showFootprint = true,
  autoRotate = false,
  enableLighting = true,
  enableBloom = true,
  simSpeed = 1,
  followSatellite = false,
  imageryStyle = "satellite",
  authToken,
  onTelemetryUpdate,
  onWsStatusChange,
}: CesiumGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);

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

  const showAllOrbitsRef = useRef(showAllOrbits);
  showAllOrbitsRef.current = showAllOrbits;

  // Persistent entity cache to avoid recreating entities on every 10s poll
  const satEntitiesRef = useRef<Map<string, SatelliteEntityRecord>>(new Map());

  // Track virtual simulated time offset (milliseconds)
  const simTimeOffsetMsRef = useRef<number>(0);
  const lastRealTimeRef = useRef<number>(Date.now());

  // Store real-time positions pushed from backend WS
  const livePositionsRef = useRef<Record<string, { lat: number; lon: number; alt: number }>>({});
  const [, setWsConnected] = useState(false);

  // Helper to get the current simulation date
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
        
        // Pass auth token if available to avoid 1008 policy violation
        const token =
          authToken ||
          (() => {
            try {
              const sessionRaw = localStorage.getItem("sb-bf2e83d0-auth-token") ||
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
            const msg = JSON.parse(event.data);
            if (msg.type === "ORBIT_UPDATE" && Array.isArray(msg.data)) {
              msg.data.forEach((update: WsOrbitUpdate) => {
                livePositionsRef.current[update.satelliteId] = {
                  lat: update.latitudeDeg,
                  lon: update.longitudeDeg,
                  alt: update.altitudeKm * 1000,
                };
              });
              // Prompt single render for live telemetry update
              if (viewerRef.current) {
                viewerRef.current.scene.requestRender();
              }
            }
          } catch {
            // Silently ignore malformed messages
          }
        };

        ws.onerror = () => {
          setWsConnected(false);
          onWsStatusChange?.(false);
        };

        ws.onclose = () => {
          setWsConnected(false);
          onWsStatusChange?.(false);
          // Retry reconnecting after 15 seconds if unmounted or disconnected
          reconnectTimeout = setTimeout(connectWs, 15_000);
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

  // 2. Initialize Cesium Viewer with High-Resolution Space & Earth Engine
  useEffect(() => {
    if (!containerRef.current) return;

    Cesium.Ion.defaultAccessToken =
      import.meta.env.VITE_CESIUM_ION_TOKEN ||
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI5NmViZGJjMS05N2Q3LTRlMTEtODNlMy05N2I2YWMyOGI1MDQiLCJpZCI6OTYxMzAsImlhdCI6MTY1NzY0MTU1N30.NImGHf1V8K8mT7MQXR6BN5sI5vmlCMTlHGnHdvFLVpM";

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

    // High performance configuration
    viewer.resolutionScale = 1.0;
    viewer.useBrowserRecommendedResolution = true;
    viewer.scene.globe.maximumScreenSpaceError = 4;
    viewer.scene.globe.tileCacheSize = 150;
    viewer.scene.globe.preloadAncestors = false;

    const scene = viewer.scene;
    scene.requestRenderMode = false; // Continuous smooth 60fps WebGL rendering so imagery tiles decode and stream immediately

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
      if ("highDynamicRange" in scene) {
        (scene as unknown as { highDynamicRange: boolean }).highDynamicRange = true;
      }
    } catch { /* ignore */ }

    try {
      if (scene.postProcessStages) {
        if (scene.postProcessStages.fxaa) {
          scene.postProcessStages.fxaa.enabled = true;
        }
        if (scene.postProcessStages.bloom) {
          scene.postProcessStages.bloom.enabled = enableBloom;
          scene.postProcessStages.bloom.uniforms.contrast = 118.0;
          scene.postProcessStages.bloom.uniforms.brightness = -0.15;
          scene.postProcessStages.bloom.uniforms.glowOnly = false;
          scene.postProcessStages.bloom.uniforms.delta = 1.0;
          scene.postProcessStages.bloom.uniforms.sigma = 2.0;
        }
      }
    } catch { /* ignore */ }

    scene.screenSpaceCameraController.minimumZoomDistance = 80_000;
    scene.screenSpaceCameraController.maximumZoomDistance = 75_000_000;

    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(20, 15, 23_500_000),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-88),
        roll: 0,
      },
    });

    const entityHandler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
    entityHandler.setInputAction((movement: { position: Cesium.Cartesian2 }) => {
      const pickedObject = scene.pick(movement.position);
      if (Cesium.defined(pickedObject) && pickedObject.id && typeof pickedObject.id.id === "string") {
        const satId = pickedObject.id.id.replace("-marker", "").replace("-pulse", "");
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

    // Frame Tick Loop for Time Warp, Auto-Rotate, and Chaser Camera
    const removeTickListener = viewer.clock.onTick.addEventListener(() => {
      const now = Date.now();
      const deltaMs = now - lastRealTimeRef.current;
      lastRealTimeRef.current = now;

      if (simSpeedRef.current > 1) {
        simTimeOffsetMsRef.current += deltaMs * (simSpeedRef.current - 1);
      }

      if (autoRotateRef.current && !followSatelliteRef.current) {
        scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, 0.0012);
      }

      if (followSatelliteRef.current && focusedIdRef.current) {
        const sat = satellitesRef.current.find((s) => s.id === focusedIdRef.current);
        if (sat) {
          const simDate = new Date(Date.now() + simTimeOffsetMsRef.current);
          const pos = computeSubSatellitePoint(sat, simDate);
          if (pos) {
            const targetPos = Cesium.Cartesian3.fromDegrees(
              pos.longitudeDeg,
              pos.latitudeDeg,
              pos.heightMeters
            );
            const range = Math.max(1_200_000, pos.heightMeters * 2.2);
            scene.camera.lookAt(
              targetPos,
              new Cesium.HeadingPitchRange(
                Cesium.Math.toRadians(45),
                Cesium.Math.toRadians(-28),
                range
              )
            );
          }
        }
      }

      // Regulated frame render: request frame only when scene state actually mutates
      if (
        autoRotateRef.current ||
        simSpeedRef.current > 1 ||
        followSatelliteRef.current ||
        focusedIdRef.current
      ) {
        scene.requestRender();
      }
    });

    viewerRef.current = viewer;
    const satEntities = satEntitiesRef.current;

    return () => {
      removeTickListener();
      entityHandler.destroy();
      viewer.destroy();
      viewerRef.current = null;
      satEntities.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 3. Dynamic High-Definition Earth Imagery Switcher
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    let isCancelled = false;

    const applyImagery = async () => {
      let provider: Cesium.ImageryProvider;
      try {
        if (imageryStyle === "satellite") {
          provider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
            "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer",
            { enablePickFeatures: false }
          );
        } else if (imageryStyle === "bluemarble") {
          provider = new Cesium.UrlTemplateImageryProvider({
            url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
            maximumLevel: 8,
            credit: "NASA GIBS Blue Marble",
          });
        } else if (imageryStyle === "night") {
          provider = new Cesium.UrlTemplateImageryProvider({
            url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_CityLights_2012/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg",
            maximumLevel: 8,
            credit: "NASA Black Marble Night Lights",
          });
        } else {
          provider = new Cesium.UrlTemplateImageryProvider({
            url: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
            subdomains: ["a", "b", "c", "d"],
            maximumLevel: 19,
            credit: "CartoDB Dark Matter",
          });
        }
      } catch (err) {
        console.warn("Primary imagery provider fallback", err);
        provider = await Cesium.TileMapServiceImageryProvider.fromUrl(
          Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")
        );
      }

      if (isCancelled || !viewerRef.current) return;

      const layers = viewer.imageryLayers;
      layers.addImageryProvider(provider);
      while (layers.length > 1) {
        layers.remove(layers.get(0));
      }
    };

    applyImagery();

    return () => {
      isCancelled = true;
    };
  }, [imageryStyle]);

  // 4. Update lighting dynamically
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer?.scene?.globe) {
      viewer.scene.globe.enableLighting = enableLighting;
      viewer.scene.requestRender();
    }
  }, [enableLighting]);

  // 5. Update HDR space bloom dynamically
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer?.scene?.postProcessStages?.bloom) {
      viewer.scene.postProcessStages.bloom.enabled = enableBloom;
      viewer.scene.requestRender();
    }
  }, [enableBloom]);

  // 6. Persistent In-Place Satellite Entity Synchronization
  // Never wipe entities every 10s! Update existing markers in-place for 0-lag instant output.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const entitiesMap = satEntitiesRef.current;
    const currentSatIds = new Set(satellites.map((s) => s.id));
    const simDate = getSimulatedDate();
    const THROTTLE_MS = 180;
    const posCache: Record<string, { pos: Cesium.Cartesian3 | undefined; ts: number }> = {};

    // A. Remove any decommissioned satellites no longer in fleet
    for (const [id, record] of entitiesMap.entries()) {
      if (!currentSatIds.has(id)) {
        viewer.entities.remove(record.marker);
        if (record.orbit) viewer.entities.remove(record.orbit);
        entitiesMap.delete(id);
      }
    }

    // B. Add new satellites or update existing ones in-place
    satellites.forEach((sat) => {
      const isFocused = sat.id === focusedIdRef.current;
      const statusColor = STATUS_COLOR[sat.status] || STATUS_COLOR.active;
      const existing = entitiesMap.get(sat.id);

      if (existing) {
        // Update existing marker attributes without destroying WebGL geometry
        if (existing.status !== sat.status) {
          existing.status = sat.status;
          if (existing.marker.point) {
            existing.marker.point.color = new Cesium.ConstantProperty(
              isFocused ? Cesium.Color.WHITE : statusColor
            );
            existing.marker.point.outlineColor = new Cesium.ConstantProperty(
              isFocused ? statusColor : Cesium.Color.fromCssColorString("#060B14")
            );
          }
        }
        return;
      }

      // Throttled position callback — pure calculation without internal render thrash
      const positionProperty = new Cesium.CallbackPositionProperty(() => {
        const now = Date.now();
        const cached = posCache[sat.id];
        if (cached && now - cached.ts < THROTTLE_MS) return cached.pos;

        const live = livePositionsRef.current[sat.id];
        let result: Cesium.Cartesian3 | undefined;
        if (live) {
          result = Cesium.Cartesian3.fromDegrees(live.lon, live.lat, live.alt);
        } else {
          const simTime = new Date(now + simTimeOffsetMsRef.current);
          const pt = computeSubSatellitePoint(sat, simTime);
          if (pt) {
            result = Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, pt.heightMeters);
          } else if (sat.longitudeDeg != null && sat.latitudeDeg != null && sat.altitudeKm != null) {
            result = Cesium.Cartesian3.fromDegrees(sat.longitudeDeg, sat.latitudeDeg, sat.altitudeKm * 1000);
          }
        }

        posCache[sat.id] = { pos: result, ts: now };
        return result;
      }, false);

      // Satellite marker entity
      const marker = viewer.entities.add({
        id: sat.id,
        name: sat.name,
        position: positionProperty,
        point: {
          pixelSize: isFocused ? 13 : 7,
          color: isFocused ? Cesium.Color.WHITE : statusColor,
          outlineColor: isFocused ? statusColor : Cesium.Color.fromCssColorString("#060B14"),
          outlineWidth: isFocused ? 3 : 1.5,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label:
          isFocused || satellites.length <= 15
            ? {
                text: sat.name,
                font: isFocused ? "bold 12px 'Inter', sans-serif" : "10px 'Inter', sans-serif",
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                fillColor: isFocused ? Cesium.Color.WHITE : Cesium.Color.fromCssColorString("#E2E8F0"),
                outlineColor: Cesium.Color.fromCssColorString("#060B14"),
                outlineWidth: 3,
                verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                pixelOffset: new Cesium.Cartesian2(0, -14),
                show: isFocused || satellites.length <= 15,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 50_000_000),
              }
            : undefined,
      });

      // 3D Orbit Trajectory ribbon:
      // Only generate polylines for the focused satellite or when fleet <= 25.
      // For 600+ satellites, generating 611 polylines simultaneously causes a 15-second browser hang.
      let orbit: Cesium.Entity | undefined;
      const shouldDrawOrbit = isFocused || (satellites.length <= 25 && showAllOrbitsRef.current);
      if (shouldDrawOrbit) {
        const orbitPoints = sampleFullOrbit3D(sat, simDate, 72);
        if (orbitPoints.length > 2) {
          const positions = orbitPoints.map((p) =>
            Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
          );
          orbit = viewer.entities.add({
            id: `${sat.id}-orbit-path`,
            polyline: {
              positions,
              width: isFocused ? 2.5 : 1.0,
              material: new Cesium.ColorMaterialProperty(statusColor.withAlpha(0.28)),
              clampToGround: false,
              show: showAllOrbitsRef.current || isFocused,
            },
          });
        }
      }

      entitiesMap.set(sat.id, { marker, orbit, status: sat.status });
    });

    viewer.scene.requestRender();
  }, [satellites, getSimulatedDate]);

  // 7. Instant Orbit Paths Visibility Toggle (0ms delay, no re-creations)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    for (const [id, record] of satEntitiesRef.current.entries()) {
      if (record.orbit && record.orbit.polyline) {
        record.orbit.polyline.show = new Cesium.ConstantProperty(
          showAllOrbits || id === focusedId
        );
      }
    }
    viewer.scene.requestRender();
  }, [showAllOrbits, focusedId]);

  // 8. Instant Focus Selection Styling & Ground Track / Footprint
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // A. Update marker styles for all existing entities in-place
    for (const [id, record] of satEntitiesRef.current.entries()) {
      const isFocused = id === focusedId;
      const statusColor = STATUS_COLOR[record.status] || STATUS_COLOR.active;

      if (record.marker.point) {
        record.marker.point.pixelSize = new Cesium.ConstantProperty(isFocused ? 13 : 7);
        record.marker.point.color = new Cesium.ConstantProperty(
          isFocused ? Cesium.Color.WHITE : statusColor
        );
        record.marker.point.outlineColor = new Cesium.ConstantProperty(
          isFocused ? statusColor : Cesium.Color.fromCssColorString("#060B14")
        );
        record.marker.point.outlineWidth = new Cesium.ConstantProperty(isFocused ? 3 : 1.5);
      }

      if (record.marker.label) {
        record.marker.label.show = new Cesium.ConstantProperty(
          isFocused || satellitesRef.current.length <= 15
        );
      }

      if (record.orbit && record.orbit.polyline) {
        record.orbit.polyline.show = new Cesium.ConstantProperty(
          showAllOrbitsRef.current || isFocused
        );
        record.orbit.polyline.width = new Cesium.ConstantProperty(isFocused ? 2.5 : 1.0);
        record.orbit.polyline.material = isFocused
          ? new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.35,
              color: statusColor.withAlpha(0.95),
            })
          : new Cesium.ColorMaterialProperty(statusColor.withAlpha(0.28));
      }
    }

    // B. Clean up previous focus-specific entities (pulse, ground track, footprint, nadir beam)
    const focusSpecific = viewer.entities.values.filter((e) =>
      e.id.startsWith("focused-track-") || e.id.endsWith("-pulse")
    );
    focusSpecific.forEach((e) => viewer.entities.remove(e));

    const focused = satellitesRef.current.find((s) => s.id === focusedId);
    if (!focused) {
      onTelemetryUpdate?.(null);
      viewer.scene.requestRender();
      return;
    }

    const simDate = getSimulatedDate();
    const statusColor = STATUS_COLOR[focused.status] || STATUS_COLOR.active;
    const record = satEntitiesRef.current.get(focused.id);
    const focusEntity = record?.marker;

    // Ensure focused satellite has its 3D orbit trajectory generated on-demand
    if (record && !record.orbit) {
      const orbitPoints = sampleFullOrbit3D(focused, simDate, 80);
      if (orbitPoints.length > 2) {
        const positions = orbitPoints.map((p) =>
          Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
        );
        record.orbit = viewer.entities.add({
          id: `${focused.id}-orbit-path`,
          polyline: {
            positions,
            width: 2.5,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.35,
              color: statusColor.withAlpha(0.95),
            }),
            clampToGround: false,
            show: true,
          },
        });
      }
    }

    // Pulsing beacon for focused satellite
    if (focusEntity) {
      viewer.entities.add({
        id: `${focused.id}-pulse`,
        name: `${focused.name} Beacon`,
        position: focusEntity.position,
        point: {
          pixelSize: new Cesium.CallbackProperty(() => {
            const t = (Date.now() % 1600) / 1600;
            return 14 + t * 18;
          }, false) as unknown as number,
          color: new Cesium.CallbackProperty(() => {
            const t = (Date.now() % 1600) / 1600;
            return statusColor.withAlpha(0.6 * (1 - t));
          }, false) as unknown as Cesium.Color,
          outlineColor: statusColor.withAlpha(0.25),
          outlineWidth: 1,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    }

    // Predicted Ground Track line
    const groundTrack = sampleGroundTrack(focused, simDate, 80);
    if (groundTrack.length > 1) {
      const positions = groundTrack.flatMap((p) => [p.longitudeDeg, p.latitudeDeg]);
      viewer.entities.add({
        id: "focused-track-polyline",
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(positions),
          width: 2.2,
          material: new Cesium.PolylineDashMaterialProperty({
            color: statusColor.withAlpha(0.85),
            gapColor: Cesium.Color.TRANSPARENT,
            dashLength: 16.0,
          }),
          clampToGround: true,
        },
      });
    }

    // Sensor Coverage Footprint
    if (showFootprint) {
      const footprintMeters = calculateFootprintRadiusMeters(focused);
      viewer.entities.add({
        id: "focused-track-footprint",
        position: new Cesium.CallbackPositionProperty(() => {
          const simTime = new Date(Date.now() + simTimeOffsetMsRef.current);
          const p = computeSubSatellitePoint(focused, simTime);
          if (p) {
            return Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, 0);
          }
          return undefined;
        }, false),
        ellipse: {
          semiMinorAxis: footprintMeters,
          semiMajorAxis: footprintMeters,
          material: statusColor.withAlpha(0.14),
          outline: true,
          outlineColor: statusColor.withAlpha(0.7),
          outlineWidth: 1.5,
          height: 10,
        },
      });

      // Nadir Beam
      viewer.entities.add({
        id: "focused-track-nadir-beam",
        polyline: {
          positions: new Cesium.CallbackProperty(() => {
            const simTime = new Date(Date.now() + simTimeOffsetMsRef.current);
            const p = computeSubSatellitePoint(focused, simTime);
            if (!p) return [];
            return [
              Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters),
              Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, 0),
            ];
          }, false),
          width: 1.5,
          material: new Cesium.PolylineDashMaterialProperty({
            color: statusColor.withAlpha(0.6),
            gapColor: Cesium.Color.TRANSPARENT,
            dashLength: 12.0,
          }),
        },
      });
    }

    // Smooth Fly-to camera
    if (!followSatelliteRef.current && focusEntity) {
      viewer.flyTo(focusEntity, {
        duration: 1.2,
        offset: new Cesium.HeadingPitchRange(
          Cesium.Math.toRadians(0),
          Cesium.Math.toRadians(-40),
          Math.max(1_600_000, (focused.altitudeKm ?? 500) * 3500)
        ),
      }).catch(() => undefined);
    }

    viewer.scene.requestRender();
  }, [focusedId, showFootprint, getSimulatedDate, onTelemetryUpdate]);

  // 9. High-Precision Live Telemetry Stream Emitter
  useEffect(() => {
    if (!focusedId || !onTelemetryUpdate) return;

    const interval = setInterval(() => {
      const focused = satellitesRef.current.find((s) => s.id === focusedId);
      if (!focused) {
        onTelemetryUpdate(null);
        return;
      }

      const simTime = new Date(Date.now() + simTimeOffsetMsRef.current);
      const live = livePositionsRef.current[focused.id];
      const propagated = computeSubSatellitePoint(focused, simTime);

      const lat = live?.lat ?? propagated?.latitudeDeg ?? focused.latitudeDeg ?? 0;
      const lon = live?.lon ?? propagated?.longitudeDeg ?? focused.longitudeDeg ?? 0;
      const altKm = live
        ? live.alt / 1000
        : propagated
        ? propagated.heightMeters / 1000
        : focused.altitudeKm ?? 0;
      const vel = calculateOrbitalVelocityKmS(focused);

      onTelemetryUpdate({
        satelliteId: focused.id,
        latitudeDeg: Math.round(lat * 1000) / 1000,
        longitudeDeg: Math.round(lon * 1000) / 1000,
        altitudeKm: Math.round(altKm * 10) / 10,
        velocityKmS: vel,
      });
    }, 200);

    return () => clearInterval(interval);
  }, [focusedId, onTelemetryUpdate]);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg bg-[#060B14]">
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}
