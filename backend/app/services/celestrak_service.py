import httpx
from fastapi import HTTPException, status
import asyncio

CELESTRAK_BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"
CELESTRAK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def fetch_tle_by_norad_id(norad_id: int, max_retries: int = 3) -> str:
    """
    Fetches the latest Two-Line Element (TLE) set for a given NORAD ID from CelesTrak.
    Returns the raw 3-line text (Name + Line 1 + Line 2).
    Includes exponential backoff retries for robustness.
    """
    url = f"{CELESTRAK_BASE_URL}?CATNR={norad_id}&FORMAT=tle"

    async with httpx.AsyncClient(headers=CELESTRAK_HEADERS) as client:
        for attempt in range(max_retries):
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
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Failed to communicate with CelesTrak: {str(exc)}"
                    )
                await asyncio.sleep(2 ** attempt)
            except httpx.HTTPStatusError as exc:
                # Don't retry on 404s
                if exc.response.status_code == 404:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No TLE data found for NORAD ID {norad_id} on CelesTrak."
                    )

                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"CelesTrak returned an error: {exc.response.status_code}"
                    )
                await asyncio.sleep(2 ** attempt)

        # If loop exhausts without returning or raising (e.g., max_retries <= 0)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch TLE data due to retry exhaustion or invalid retry count."
        )
