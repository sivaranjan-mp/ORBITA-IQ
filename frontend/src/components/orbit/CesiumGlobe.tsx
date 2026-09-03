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
  onTelemetryUpdate?: (telemetry: LiveTelemetry | null) => void;
  onWsStatusChange?: (connected: boolean) => void;
}

interface WsOrbitUpdate {
  satelliteId: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
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

  // 1. Graceful WebSocket connection to backend
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
        const wsUrl = `${wsBase}/orbit/ws`;

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
          // Try reconnecting after 10 seconds
          reconnectTimeout = setTimeout(connectWs, 10_000);
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
  }, [onWsStatusChange]);

  // 2. Initialize Cesium Viewer with High-Resolution Space & Earth Engine
  useEffect(() => {
    if (!containerRef.current) return;

    // Use real public Cesium Ion default token — allows terrain & built-in assets
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
      // Provide a guaranteed offline base layer so the globe always renders
      baseLayer: Cesium.ImageryLayer.fromProviderAsync(
        Cesium.TileMapServiceImageryProvider.fromUrl(
          Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")
        ),
        {}
      ),
      contextOptions: {
        webgl: {
          alpha: false, // Deep space opaque rendering for maximum contrast & crisp stars
          preserveDrawingBuffer: true,
          powerPreference: "high-performance",
        },
      },
    });

    // Clean aesthetic: Hide Cesium credit container overlay
    if (viewer.cesiumWidget.creditContainer) {
      (viewer.cesiumWidget.creditContainer as HTMLElement).style.display = "none";
    }

    // High-Resolution & Sharpness Configuration
    viewer.resolutionScale = Math.min(window.devicePixelRatio || 1, 2.0);
    viewer.useBrowserRecommendedResolution = false;
    viewer.scene.globe.maximumScreenSpaceError = 1.25; // Sharper tile LOD (higher texture detail)
    viewer.scene.globe.tileCacheSize = 350;

    const scene = viewer.scene;

    // Deep Space Cosmic Colors
    scene.globe.baseColor = Cesium.Color.fromCssColorString("#02050D");
    scene.backgroundColor = Cesium.Color.fromCssColorString("#010204");
    scene.globe.enableLighting = enableLighting;

    // Authentic Tycho-2 Deep Space Starfield SkyBox
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

    // Photorealistic Atmospheric Scattering (Earth Glow)
    scene.globe.showGroundAtmosphere = true;
    scene.globe.atmosphereLightIntensity = 15.0;
    scene.globe.atmosphereRayleighScaleHeight = 8500.0;
    scene.globe.atmosphereMieScaleHeight = 1200.0;
    scene.globe.lightingFadeInDistance = 25000000.0;
    scene.globe.lightingFadeOutDistance = 15000000.0;
    scene.globe.nightFadeInDistance = 15000000.0;
    scene.globe.nightFadeOutDistance = 60000000.0;

    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.atmosphereLightIntensity = 14.0;
      scene.skyAtmosphere.saturationShift = 0.45;
      scene.skyAtmosphere.brightnessShift = 0.20;
      scene.skyAtmosphere.hueShift = -0.02; // Vivid orbital cyan-blue rim halo
    }

    if (scene.sun) scene.sun.show = true;
    if (scene.moon) scene.moon.show = true;

    // High Dynamic Range & Space Bloom Post-Processing
    try {
      if ("highDynamicRange" in scene) {
        (scene as unknown as { highDynamicRange: boolean }).highDynamicRange = true;
      }
    } catch { /* HDR not supported in this build */ }

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
    } catch { /* Post-processing not available */ }

    // Zoom limits
    scene.screenSpaceCameraController.minimumZoomDistance = 80_000;
    scene.screenSpaceCameraController.maximumZoomDistance = 75_000_000;

    // Initial camera position framed over Earth
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(20, 15, 23_500_000),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-88),
        roll: 0,
      },
    });

    // Selection listener
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
      // Clicked on empty space
      if (!pickedObject) {
        onSelect(null);
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Frame Tick Loop for Time Warp, Auto-Rotate, and Chaser Camera
    const removeTickListener = viewer.clock.onTick.addEventListener(() => {
      const now = Date.now();
      const deltaMs = now - lastRealTimeRef.current;
      lastRealTimeRef.current = now;

      // Advance simulation time offset according to speed multiplier
      if (simSpeedRef.current > 1) {
        simTimeOffsetMsRef.current += deltaMs * (simSpeedRef.current - 1);
      }

      // Continuous Earth Auto-Rotation when enabled and not following a satellite
      if (autoRotateRef.current && !followSatelliteRef.current) {
        scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, 0.0012);
      }

      // Chaser Camera: Smoothly follow the focused satellite in orbit
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
    });

    viewerRef.current = viewer;

    return () => {
      removeTickListener();
      entityHandler.destroy();
      viewer.destroy();
      viewerRef.current = null;
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
          // ESRI World Imagery (High-Resolution Global Satellite Photography)
          provider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
            "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer",
            { enablePickFeatures: false }
          );
        } else if (imageryStyle === "bluemarble") {
          // NASA GIBS Blue Marble with Bathymetry & Shaded Relief
          provider = new Cesium.UrlTemplateImageryProvider({
            url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
            maximumLevel: 8,
            credit: "NASA GIBS Blue Marble",
          });
        } else if (imageryStyle === "night") {
          // NASA Black Marble (Earth at Night / Golden City Lights)
          provider = new Cesium.UrlTemplateImageryProvider({
            url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_CityLights_2012/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg",
            maximumLevel: 8,
            credit: "NASA Black Marble Night Lights",
          });
        } else {
          // Tactical Deep Space / CartoDB Dark Matter
          provider = new Cesium.UrlTemplateImageryProvider({
            url: "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
            subdomains: ["a", "b", "c", "d"],
            maximumLevel: 19,
            credit: "CartoDB Dark Matter",
          });
        }
      } catch (err) {
        console.warn("Primary imagery provider failed, using NaturalEarthII fallback", err);
        provider = await Cesium.TileMapServiceImageryProvider.fromUrl(
          Cesium.buildModuleUrl("Assets/Textures/NaturalEarthII")
        );
      }

      if (isCancelled || !viewerRef.current) return;

      const layers = viewer.imageryLayers;
      layers.removeAll();
      layers.addImageryProvider(provider);
    };

    applyImagery();

    return () => {
      isCancelled = true;
    };
  }, [imageryStyle]);

  // 4. Update lighting dynamically
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer && viewer.scene && viewer.scene.globe) {
      viewer.scene.globe.enableLighting = enableLighting;
    }
  }, [enableLighting]);

  // 5. Update HDR space bloom dynamically
  useEffect(() => {
    const viewer = viewerRef.current;
    if (viewer && viewer.scene && viewer.scene.postProcessStages?.bloom) {
      viewer.scene.postProcessStages.bloom.enabled = enableBloom;
    }
  }, [enableBloom]);

  // 4. Populate Satellite Entities and 3D Trajectories
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Clear previous satellite entities (preserve ground track if any)
    const entitiesToRemove = viewer.entities.values.filter(
      (e) => !e.id.startsWith("focused-track-")
    );
    entitiesToRemove.forEach((e) => viewer.entities.remove(e));

    const simDate = getSimulatedDate();

    satellites.forEach((sat) => {
      const isFocused = sat.id === focusedId;
      const statusColor = STATUS_COLOR[sat.status] || STATUS_COLOR.active;

      // Dynamic position property that updates in real time
      const positionProperty = new Cesium.CallbackPositionProperty(() => {
        // Priority 1: Backend WebSocket live push
        const live = livePositionsRef.current[sat.id];
        if (live) {
          return Cesium.Cartesian3.fromDegrees(live.lon, live.lat, live.alt);
        }

        // Priority 2: High-precision real-time orbit propagation
        const simTime = new Date(Date.now() + simTimeOffsetMsRef.current);
        const pt = computeSubSatellitePoint(sat, simTime);
        if (pt) {
          return Cesium.Cartesian3.fromDegrees(pt.longitudeDeg, pt.latitudeDeg, pt.heightMeters);
        }

        // Priority 3: Static fallback from initial payload
        if (sat.longitudeDeg != null && sat.latitudeDeg != null && sat.altitudeKm != null) {
          return Cesium.Cartesian3.fromDegrees(
            sat.longitudeDeg,
            sat.latitudeDeg,
            sat.altitudeKm * 1000
          );
        }

        return undefined;
      }, false);

      // Add Satellite Marker Entity
      viewer.entities.add({
        id: sat.id,
        name: sat.name,
        position: positionProperty,
        point: {
          pixelSize: isFocused ? 14 : 9,
          color: isFocused ? Cesium.Color.WHITE : statusColor,
          outlineColor: isFocused ? statusColor : Cesium.Color.fromCssColorString("#060B14"),
          outlineWidth: isFocused ? 3.5 : 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
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
        },
      });

      // Animated Pulsing Beacon for Focused Satellite
      if (isFocused) {
        viewer.entities.add({
          id: `${sat.id}-pulse`,
          name: `${sat.name} Beacon`,
          position: positionProperty,
          point: {
            pixelSize: new Cesium.CallbackProperty(() => {
              const t = (Date.now() % 1500) / 1500;
              return 16 + t * 24;
            }, false) as unknown as number,
            color: new Cesium.CallbackProperty(() => {
              const t = (Date.now() % 1500) / 1500;
              return statusColor.withAlpha(0.7 * (1 - t));
            }, false) as unknown as Cesium.Color,
            outlineColor: statusColor.withAlpha(0.3),
            outlineWidth: 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        });
      }

      // Draw 3D Orbit Trajectory Line (Glowing neon ribbon)
      if (showAllOrbits || isFocused) {
        const orbitPoints = sampleFullOrbit3D(sat, simDate, 100);
        if (orbitPoints.length > 2) {
          const positions = orbitPoints.map((p) =>
            Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters)
          );

          viewer.entities.add({
            id: `${sat.id}-orbit-path`,
            polyline: {
              positions,
              width: isFocused ? 2.8 : 1.2,
              material: new Cesium.PolylineGlowMaterialProperty({
                glowPower: isFocused ? 0.4 : 0.15,
                color: statusColor.withAlpha(isFocused ? 0.95 : 0.35),
              }),
              clampToGround: false,
            },
          });
        }
      }
    });
  }, [satellites, focusedId, showAllOrbits, getSimulatedDate]);

  // 5. Draw Ground Track, Nadir Beam, and Coverage Footprint for Focused Satellite
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    // Remove any previous focused ground track entities
    const trackEntities = viewer.entities.values.filter((e) =>
      e.id.startsWith("focused-track-")
    );
    trackEntities.forEach((e) => viewer.entities.remove(e));

    const focused = satellitesRef.current.find((s) => s.id === focusedId);
    if (!focused) {
      onTelemetryUpdate?.(null);
      return;
    }

    const simDate = getSimulatedDate();
    const statusColor = STATUS_COLOR[focused.status] || STATUS_COLOR.active;

    // 1. Predicted Ground Track on Earth surface
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

    // 2. Sensor Coverage Footprint (Nadir projected ellipse on ground)
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

      // Nadir Beam: Line connecting satellite to sub-satellite ground point
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

    // Smooth Fly-to camera animation if not in follow mode
    if (!followSatelliteRef.current) {
      const entity = viewer.entities.getById(focused.id);
      if (entity) {
        viewer.flyTo(entity, {
          duration: 1.6,
          offset: new Cesium.HeadingPitchRange(
            Cesium.Math.toRadians(0),
            Cesium.Math.toRadians(-40),
            Math.max(1_600_000, (focused.altitudeKm ?? 500) * 3500)
          ),
        }).catch(() => undefined);
      }
    }
  }, [focusedId, showFootprint, getSimulatedDate, onTelemetryUpdate]);

  // 6. Live Telemetry stream emitter to parent
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
      const altKm = live ? live.alt / 1000 : (propagated ? propagated.heightMeters / 1000 : focused.altitudeKm ?? 0);
      const vel = calculateOrbitalVelocityKmS(focused);

      onTelemetryUpdate({
        satelliteId: focused.id,
        latitudeDeg: Math.round(lat * 100) / 100,
        longitudeDeg: Math.round(lon * 100) / 100,
        altitudeKm: Math.round(altKm * 10) / 10,
        velocityKmS: vel,
      });
    }, 250);

    return () => clearInterval(interval);
  }, [focusedId, onTelemetryUpdate]);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg bg-[#060B14]">
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}
