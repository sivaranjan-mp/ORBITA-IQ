from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"


class SatelliteStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    INACTIVE = "inactive"
    DECAYED = "decayed"


class ObjectType(str, Enum):
    PAYLOAD = "payload"
    DEBRIS = "debris"
    ROCKET_BODY = "rocket_body"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConjunctionStatus(str, Enum):
    OPEN = "open"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AlertState(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ManeuverDirection(str, Enum):
    ALONG_TRACK_EARLIER = "along_track_earlier"
    ALONG_TRACK_LATER = "along_track_later"
    RADIAL_POSITIVE = "radial_positive"
    RADIAL_NEGATIVE = "radial_negative"
    CROSS_TRACK_POSITIVE = "cross_track_positive"
    CROSS_TRACK_NEGATIVE = "cross_track_negative"

