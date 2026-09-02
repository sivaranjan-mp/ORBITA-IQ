export interface CatalogItem {
  noradId: number;
  name: string;
  internationalDesignator?: string | null;
  objectType: "payload" | "rocket_body" | "debris" | "unknown";
  orbitRegime: "LEO" | "MEO" | "GEO" | "HEO" | "OTHER";
  apogeeKm?: number | null;
  perigeeKm?: number | null;
  inclinationDeg?: number | null;
  periodMinutes?: number | null;
  isTracked: boolean;
  trackedSatelliteId?: string | null;
  epoch?: string | null;
}

export interface CatalogListResponse {
  items: CatalogItem[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface CatalogSyncResponse {
  syncedCount: number;
  message: string;
}
