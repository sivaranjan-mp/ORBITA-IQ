from datetime import datetime

def parse_omm_json(payload: dict) -> dict:
    """
    Parses a CCSDS OMM (Orbit Data Message) JSON payload 
    to extract standard orbital elements.
    """
    epoch_str = payload.get("EPOCH")
    epoch_ts = None
    if epoch_str:
        # Handle 'Z' to '+00:00' for ISO format parsing
        epoch_ts = datetime.fromisoformat(epoch_str.replace("Z", "+00:00"))
        
    return {
        "norad_id": payload.get("NORAD_CAT_ID"),
        "name": payload.get("OBJECT_NAME", "Unknown"),
        "epoch": epoch_ts,
        "mean_motion": payload.get("MEAN_MOTION"),
        "eccentricity": payload.get("ECCENTRICITY"),
        "inclination": payload.get("INCLINATION"),
        "raan": payload.get("RA_OF_ASC_NODE"),
        "arg_of_pericenter": payload.get("ARG_OF_PERICENTER"),
        "mean_anomaly": payload.get("MEAN_ANOMALY"),
        "bstar": payload.get("BSTAR"),
        "classification": payload.get("CLASSIFICATION_TYPE", "U"),
        "ephemeris_type": payload.get("EPHEMERIS_TYPE")
    }
