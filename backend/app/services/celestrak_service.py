import httpx
from fastapi import HTTPException, status

CELESTRAK_BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"

async def fetch_tle_by_norad_id(norad_id: int) -> str:
    """
    Fetches the latest Two-Line Element (TLE) set for a given NORAD ID from CelesTrak.
    Returns the raw 3-line text (Name + Line 1 + Line 2).
    """
    url = f"{CELESTRAK_BASE_URL}?CATNR={norad_id}&FORMAT=tle"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            text = response.text.strip()
            
            if "No GP data found" in text or text == "":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No TLE data found for NORAD ID {norad_id} on CelesTrak."
                )
            
            # Basic validation that we received at least 2 lines (ideally 3 with name)
            lines = text.split("\n")
            if len(lines) < 2:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid TLE format received from CelesTrak."
                )
                
            return text
            
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to communicate with CelesTrak: {str(exc)}"
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"CelesTrak returned an error: {exc.response.status_code}"
            )
