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
