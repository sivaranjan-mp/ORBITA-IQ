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

if (typeof window !== "undefined") {
  (window as unknown as { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = "/cesium/";
}

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

export function CesiumGlobe({
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
    viewer.scene.globe.maximumScreenSpaceError = 4;
    viewer.scene.globe.tileCacheSize = 200;
    viewer.scene.globe.preloadAncestors = false;

    const scene = viewer.scene;
    // Continuous 60fps WebGL rendering so tiles and satellites NEVER freeze or stay black
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

    // Camera zoom boundaries
    scene.screenSpaceCameraController.minimumZoomDistance = 150_000;
    scene.screenSpaceCameraController.maximumZoomDistance = 35_000_000;
    scene.screenSpaceCameraController.enableCollisionDetection = true;

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

    // 60fps Frame Tick Loop for Time Warp, Auto-Rotate, Chaser Cam, and GPU Points
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

      const simDate = new Date(Date.now() + simTimeOffsetMsRef.current);

      // Fast update all 611 satellite coordinates on the GPU in <1ms
      const pointsMap = pointsMapRef.current;
      satellitesRef.current.forEach((sat) => {
        const p = pointsMap.get(sat.id);
        if (!p) return;
        const live = livePositionsRef.current[sat.id];
        if (live) {
          p.position = Cesium.Cartesian3.fromDegrees(live.lon, live.lat, live.alt);
        } else {
          const sub = computeSubSatellitePoint(sat, simDate);
          if (sub) {
            p.position = Cesium.Cartesian3.fromDegrees(sub.longitudeDeg, sub.latitudeDeg, sub.heightMeters);
          }
        }
      });

      // Update focused label position
      if (focusedLabelRef.current && focusedIdRef.current) {
        const sat = satellitesRef.current.find((s) => s.id === focusedIdRef.current);
        if (sat) {
          const sub = computeSubSatellitePoint(sat, simDate);
          if (sub) {
            focusedLabelRef.current.position = Cesium.Cartesian3.fromDegrees(
              sub.longitudeDeg,
              sub.latitudeDeg,
              sub.heightMeters
            );
          }
        }
      }

      // Camera chaser follow mode
      if (followSatelliteRef.current && focusedIdRef.current) {
        const sat = satellitesRef.current.find((s) => s.id === focusedIdRef.current);
        if (sat) {
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
      const statusColor = STATUS_COLOR[sat.status] || STATUS_COLOR.active;
      const pt = computeSubSatellitePoint(sat, simDate);
      if (!pt) return;

      const position = Cesium.Cartesian3.fromDegrees(
        pt.longitudeDeg,
        pt.latitudeDeg,
        pt.heightMeters
      );

      const existing = pointsMap.get(sat.id);
      if (existing) {
        existing.position = position;
        existing.pixelSize = isFocused ? 14 : 7;
        existing.color = isFocused ? Cesium.Color.WHITE : statusColor;
        existing.outlineColor = isFocused ? statusColor : Cesium.Color.fromCssColorString("#060B14");
        existing.outlineWidth = isFocused ? 3 : 1.5;
      } else {
        const point = pointCollection.add({
          position,
          pixelSize: isFocused ? 14 : 7,
          color: isFocused ? Cesium.Color.WHITE : statusColor,
          outlineColor: isFocused ? statusColor : Cesium.Color.fromCssColorString("#060B14"),
          outlineWidth: isFocused ? 3 : 1.5,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          id: sat.id,
        });
        pointsMap.set(sat.id, point);
      }
    });
  }, [satellites, getSimulatedDate]);

  // 7. Render 3D Orbital Trajectories for Fleet
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

    satellitesToRender.forEach((sat) => {
      const isFocused = sat.id === focusedId;
      const orbitPoints = sampleFullOrbit3D(sat, simDate, isFocused ? 72 : 48);
      if (orbitPoints.length < 3) return;

      const positions = orbitPoints.map((p) =>
        Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
      );

      const statusColor = STATUS_COLOR[sat.status] || STATUS_COLOR.active;
      const lineColor = isFocused
        ? Cesium.Color.fromCssColorString("#00F2FE").withAlpha(0.95)
        : statusColor.withAlpha(0.4);

      const polyline = polylineCollection.add({
        positions,
        width: isFocused ? 2.5 : 1.2,
        material: Cesium.Material.fromType("Color", {
          color: lineColor,
        }),
      });

      polylinesMap.set(sat.id, polyline);
    });
  }, [satellites, showAllOrbits, focusedId, getSimulatedDate]);

  // 8. Instant Focus Selection Styling & Ground Track / Footprint
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Update point colors in PointPrimitiveCollection
    const pointsMap = pointsMapRef.current;
    for (const [id, pt] of pointsMap.entries()) {
      const isFocused = id === focusedId;
      const sat = satellitesRef.current.find((s) => s.id === id);
      const statusColor = sat ? STATUS_COLOR[sat.status] || STATUS_COLOR.active : STATUS_COLOR.active;
      pt.pixelSize = isFocused ? 14 : 7;
      pt.color = isFocused ? Cesium.Color.WHITE : statusColor;
      pt.outlineColor = isFocused ? statusColor : Cesium.Color.fromCssColorString("#060B14");
      pt.outlineWidth = isFocused ? 3 : 1.5;
    }

    // Clean up previous focus entities (ground track, footprint, nadir beam)
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
    const statusColor = STATUS_COLOR[focused.status] || STATUS_COLOR.active;
    const pt = computeSubSatellitePoint(focused, simDate);
    if (!pt) return;

    const focusedPos = Cesium.Cartesian3.fromDegrees(
      pt.longitudeDeg,
      pt.latitudeDeg,
      pt.heightMeters
    );

    // Label for focused satellite
    if (labelCollectionRef.current) {
      focusedLabelRef.current = labelCollectionRef.current.add({
        position: focusedPos,
        text: focused.name,
        font: "bold 13px 'Inter', sans-serif",
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.fromCssColorString("#060B14"),
        outlineWidth: 3,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -16),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      });
    }

    // Nadir Ground Footprint Disk
    if (showFootprint) {
      const footprintRadius = calculateFootprintRadiusMeters(focused);
      viewer.entities.add({
        id: "focused-footprint",
        position: Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, 0),
        ellipse: {
          semiMajorAxis: footprintRadius,
          semiMinorAxis: footprintRadius,
          material: statusColor.withAlpha(0.12),
          outline: true,
          outlineColor: statusColor.withAlpha(0.6),
          outlineWidth: 1.5,
          height: 100,
        },
      });
    }

    // Ground Track Line
    const groundTrackPoints = sampleGroundTrack(focused, simDate, 60);
    if (groundTrackPoints.length > 2) {
      viewer.entities.add({
        id: "focused-ground-track",
        polyline: {
          positions: groundTrackPoints.map((p) =>
            Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, 500)
          ),
          width: 2.0,
          material: new Cesium.PolylineDashMaterialProperty({
            color: Cesium.Color.fromCssColorString("#F5A623").withAlpha(0.75),
            dashLength: 12.0,
          }),
        },
      });
    }

    // Update real-time telemetry callback
    const velocity = calculateOrbitalVelocityKmS(focused);
    onTelemetryUpdate?.({
      satelliteId: focused.id,
      latitudeDeg: pt.latitudeDeg,
      longitudeDeg: pt.longitudeDeg,
      altitudeKm: pt.heightMeters / 1000,
      velocityKmS: velocity,
    });

    // Camera fly-to with wide full horizontal orbital perspective
    const range = Math.max(4_500_000, pt.heightMeters * 3.5);
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        pt.longitudeDeg,
        pt.latitudeDeg - 10,
        pt.heightMeters + range
      ),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-45),
        roll: 0.0,
      },
      duration: 1.2,
    });
  }, [focusedId, showFootprint, getSimulatedDate, onTelemetryUpdate]);

  // 8. Fleet Orbits and Footprints (Rendered for My Fleet <= 25 satellites)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Clean previous fleet entities
    const fleetEntities = viewer.entities.values.filter((e) =>
      e.id.startsWith("fleet-orbit-") || e.id.startsWith("fleet-footprint-")
    );
    fleetEntities.forEach((e) => viewer.entities.remove(e));

    if (satellites.length <= 25) {
      const simDate = getSimulatedDate();
      satellites.forEach((sat) => {
        if (sat.id === focusedId) return; // focused satellite has its own highlighted entities

        const statusColor = STATUS_COLOR[sat.status] || STATUS_COLOR.active;

        // 3D Orbit ribbon for all my fleet satellites
        if (showAllOrbits) {
          const orbitPoints = sampleFullOrbit3D(sat, simDate, 72);
          if (orbitPoints.length > 2) {
            const positions = orbitPoints.map((p) =>
              Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
            );
            viewer.entities.add({
              id: `fleet-orbit-${sat.id}`,
              polyline: {
                positions,
                width: 1.2,
                material: new Cesium.ColorMaterialProperty(statusColor.withAlpha(0.35)),
                clampToGround: false,
                show: true,
              },
            });
          }
        }

        // Coverage Footprint ellipse for all my fleet satellites
        if (showFootprint) {
          const footprintMeters = calculateFootprintRadiusMeters(sat);
          viewer.entities.add({
            id: `fleet-footprint-${sat.id}`,
            position: new Cesium.CallbackPositionProperty(() => {
              const simTime = new Date(Date.now() + simTimeOffsetMsRef.current);
              const p = computeSubSatellitePoint(sat, simTime);
              if (!p) return undefined;
              return Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, 0);
            }, false),
            ellipse: {
              semiMajorAxis: footprintMeters,
              semiMinorAxis: footprintMeters,
              material: new Cesium.ColorMaterialProperty(statusColor.withAlpha(0.08)),
              outline: true,
              outlineColor: new Cesium.ConstantProperty(statusColor.withAlpha(0.35)),
              outlineWidth: 1.0,
              height: 0,
            },
          });
        }
      });
    }
  }, [satellites, showAllOrbits, showFootprint, focusedId, getSimulatedDate]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 w-full h-full min-h-[450px] overflow-hidden select-none bg-[#010204]"
    />
  );
}
