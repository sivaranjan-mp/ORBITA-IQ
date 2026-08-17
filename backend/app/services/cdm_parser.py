from datetime import datetime

def parse_cdm_json(payload: dict) -> dict:
    """
    Parses a CCSDS CDM (Conjunction Data Message) JSON payload 
    to extract conjunction metrics.
    """
    tca_str = payload.get("TCA")
    tca_ts = None
    if tca_str:
        tca_ts = datetime.fromisoformat(tca_str.replace("Z", "+00:00"))
        
    # Space-Track CDM XML/JSON often uses SAT_1_ID and SAT_2_ID or similar variants
    primary_norad_id = payload.get("SAT_1_ID") or payload.get("SAT1_NORAD_CAT_ID") or payload.get("SAT1_ID")
    secondary_norad_id = payload.get("SAT_2_ID") or payload.get("SAT2_NORAD_CAT_ID") or payload.get("SAT2_ID")
        
    return {
        "primary_norad_id": int(primary_norad_id) if primary_norad_id else None,
        "secondary_norad_id": int(secondary_norad_id) if secondary_norad_id else None,
        "tca": tca_ts,
        "miss_distance": payload.get("MISS_DISTANCE"),
        "collision_probability": payload.get("COLLISION_PROBABILITY"),
        "time_of_message": payload.get("CREATION_DATE")
    }
