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
  status: string;
}

export interface CatalogSyncStatus {
  status: "idle" | "running" | "completed" | "failed";
  processed: number;
  total: number;
  percent: number;
  syncedCount: number;
  startedAt?: string | null;
  completedAt?: string | null;
  error?: string | null;
  message?: string | null;
}
