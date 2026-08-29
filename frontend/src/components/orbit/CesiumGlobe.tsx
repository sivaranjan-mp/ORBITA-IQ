import { useEffect, useRef } from "react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

// import { computeSubSatellitePoint, sampleGroundTrack } from "@/lib/orbitPropagation";
import type { Satellite, SatelliteStatus } from "@/types/satellite";

const STATUS_COLOR: Record<SatelliteStatus, Cesium.Color> = {
  active: Cesium.Color.fromCssColorString("#35C7C1"),
  degraded: Cesium.Color.fromCssColorString("#F5A623"),
  inactive: Cesium.Color.fromCssColorString("#8B98B3"),
  decayed: Cesium.Color.fromCssColorString("#F2545B"),
};

interface CesiumGlobeProps {
  satellites: Satellite[];
  focusedId: string | null;
  onSelect: (satelliteId: string | null) => void;
}

interface WsOrbitUpdate {
  satelliteId: string;
  latitudeDeg: number;
  longitudeDeg: number;
  altitudeKm: number;
}

export function CesiumGlobe({ satellites, focusedId, onSelect }: CesiumGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const satellitesRef = useRef(satellites);
  satellitesRef.current = satellites;

  // Store real-time positions pushed from backend WS
  const livePositionsRef = useRef<Record<string, { lat: number; lon: number; alt: number }>>({});

  useEffect(() => {
    const wsUrl = import.meta.env.VITE_API_URL 
      ? import.meta.env.VITE_API_URL.replace("http", "ws") + "/orbit/ws"
      : (() => { throw new Error("Missing VITE_API_BASE_URL for WebSocket connection."); })();
    
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "ORBIT_UPDATE") {
          msg.data.forEach((update: WsOrbitUpdate) => {
            livePositionsRef.current[update.satelliteId] = {
              lat: update.latitudeDeg,
              lon: update.longitudeDeg,
              alt: update.altitudeKm * 1000
            };
          });
        }
      } catch (e) {
        console.error("WS parse error", e);
      }
    };
    return () => ws.close();
  }, []);

  // Create the viewer once.
  useEffect(() => {
    if (!containerRef.current) return;

    const viewer = new Cesium.Viewer(containerRef.current, {
      baseLayer: Cesium.ImageryLayer.fromProviderAsync(
        Promise.resolve(
          new Cesium.OpenStreetMapImageryProvider({ url: "https://tile.openstreetmap.org/" })
        )
      ),
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      infoBox: true,
      selectionIndicator: true,
      shouldAnimate: true,
    });

    viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0B1220");
    if (viewer.scene.skyAtmosphere) {
      viewer.scene.skyAtmosphere.hueShift = -0.1;
    }
    viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#0B1220");
    viewer.scene.moon = undefined as unknown as Cesium.Scene["moon"];
    viewer.clock.shouldAnimate = true;

    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(0, 10, 22_000_000),
    });

    viewer.selectedEntityChanged.addEventListener((entity) => {
      onSelect(entity ? String(entity.id) : null);
    });

    viewerRef.current = viewer;

    return () => {
      viewer.destroy();
      viewerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync satellite entities whenever the fleet changes.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    viewer.entities.removeAll();

    for (const sat of satellites) {
      viewer.entities.add({
        id: sat.id,
        name: sat.name,
        position: new Cesium.CallbackPositionProperty(() => {
          // --- Feature Flagged: Client-side propagation ---
          // const p = computeSubSatellitePoint(sat, new Date());
          // return Cesium.Cartesian3.fromDegrees(p.longitudeDeg, p.latitudeDeg, p.heightMeters);

          // --- New: Real-time from backend WS ---
          const p = livePositionsRef.current[sat.id];
          if (p) {
             return Cesium.Cartesian3.fromDegrees(p.lon, p.lat, p.alt);
          }
          // Fallback to static point from initial API payload
          const fallbackLon = sat.longitudeDeg || 0;
          const fallbackLat = sat.latitudeDeg || 0;
          const fallbackAlt = (sat.altitudeKm || 0) * 1000;
          return Cesium.Cartesian3.fromDegrees(fallbackLon, fallbackLat, fallbackAlt);
        }, false),
        point: {
          pixelSize: 8,
          color: STATUS_COLOR[sat.status],
          outlineColor: Cesium.Color.fromCssColorString("#0B1220"),
          outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        description: `
          <table>
            <tr><td>NORAD ID</td><td>${sat.noradId}</td></tr>
            <tr><td>Owner</td><td>${sat.ownerOrg}</td></tr>
            <tr><td>Altitude</td><td>${sat.altitudeKm != null ? `${sat.altitudeKm} km` : "N/A"}</td></tr>
            <tr><td>Inclination</td><td>${sat.inclinationDeg != null ? `${sat.inclinationDeg.toFixed(1)}°` : "N/A"}</td></tr>
            <tr><td>Period</td><td>${sat.periodMinutes != null ? `${sat.periodMinutes.toFixed(1)} min` : "N/A"}</td></tr>
          </table>
        `,
      });
    }
  }, [satellites]);

  // Draw / clear the predicted ground track for the focused satellite.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const trackId = "ground-track";
    const existing = viewer.entities.getById(trackId);
    if (existing) viewer.entities.remove(existing);

    const focused = satellitesRef.current.find((s) => s.id === focusedId);
    if (!focused) return;

    // --- Feature Flagged: Client-side ground track ---
    // const track = sampleGroundTrack(focused, new Date());
    // const positions = track.flatMap((p) => [p.longitudeDeg, p.latitudeDeg]);
    //
    // viewer.entities.add({
    //   id: trackId,
    //   polyline: {
    //     positions: Cesium.Cartesian3.fromDegreesArray(positions),
    //     width: 1.5,
    //     material: new Cesium.PolylineDashMaterialProperty({
    //       color: Cesium.Color.fromCssColorString("#35C7C1").withAlpha(0.6),
    //     }),
    //     clampToGround: false,
    //   },
    // });

    const entity = viewer.entities.getById(focused.id);
    if (entity) {
      viewer.flyTo(entity, { duration: 1.2 }).catch(() => undefined);
    }
  }, [focusedId]);

  return <div ref={containerRef} className="h-full w-full overflow-hidden rounded-lg" />;
}
