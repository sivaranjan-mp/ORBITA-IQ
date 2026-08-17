import type { ConjunctionAlert } from "@/types/alert";

const now = Date.now();
const hours = (h: number) => new Date(now + h * 3600_000).toISOString();

export const MOCK_ALERTS: ConjunctionAlert[] = [
  {
    id: "cdm-1001",
    primarySatellite: "ISS (ZARYA)",
    primaryNoradId: 25544,
    secondaryObject: "COSMOS 2251 DEB",
    secondaryNoradId: 33591,
    tca: hours(6.2),
    missDistanceM: 340,
    relativeVelocityKmS: 14.5,
    probability: 0.00042,
    riskLevel: "critical",
    status: "open",
    detectedBy: "satguard",
    createdAt: hours(-2),
  },
  {
    id: "cdm-1002",
    primarySatellite: "STARLINK-3011",
    primaryNoradId: 48274,
    secondaryObject: "FENGYUN 1C DEB",
    secondaryNoradId: 29657,
    tca: hours(14.8),
    missDistanceM: 1120,
    relativeVelocityKmS: 12.1,
    probability: 0.000037,
    riskLevel: "high",
    status: "monitoring",
    detectedBy: "satguard",
    createdAt: hours(-5),
  },
  {
    id: "cdm-1003",
    primarySatellite: "NOAA-20",
    primaryNoradId: 43013,
    secondaryObject: "SL-16 R/B",
    secondaryNoradId: 22285,
    tca: hours(28.4),
    missDistanceM: 2870,
    relativeVelocityKmS: 13.8,
    probability: 0.0000041,
    riskLevel: "medium",
    status: "monitoring",
    detectedBy: "cdm_upload",
    createdAt: hours(-9),
  },
  {
    id: "cdm-1004",
    primarySatellite: "METEOR-M2",
    primaryNoradId: 40069,
    secondaryObject: "IRIDIUM 33 DEB",
    secondaryNoradId: 34454,
    tca: hours(41.1),
    missDistanceM: 5400,
    relativeVelocityKmS: 8.2,
    probability: 0.0000006,
    riskLevel: "low",
    status: "open",
    detectedBy: "satguard",
    createdAt: hours(-1),
  },
  {
    id: "cdm-1005",
    primarySatellite: "AQUA",
    primaryNoradId: 27424,
    secondaryObject: "UNKNOWN OBJECT",
    secondaryNoradId: 51022,
    tca: hours(-3.5),
    missDistanceM: 980,
    relativeVelocityKmS: 11.4,
    probability: 0.000012,
    riskLevel: "high",
    status: "resolved",
    detectedBy: "satguard",
    createdAt: hours(-30),
  },
  {
    id: "cdm-1006",
    primarySatellite: "STARLINK-1130",
    primaryNoradId: 44713,
    secondaryObject: "COSMOS 1408 DEB",
    secondaryNoradId: 49271,
    tca: hours(52.6),
    missDistanceM: 3210,
    relativeVelocityKmS: 10.9,
    probability: 0.0000019,
    riskLevel: "medium",
    status: "dismissed",
    detectedBy: "manual",
    createdAt: hours(-18),
  },
];

export function getUpcomingAlert(alerts: ConjunctionAlert[]): ConjunctionAlert | null {
  const upcoming = alerts
    .filter((a) => new Date(a.tca).getTime() > Date.now() && a.status !== "dismissed")
    .sort((a, b) => new Date(a.tca).getTime() - new Date(b.tca).getTime());
  return upcoming[0] ?? null;
}
