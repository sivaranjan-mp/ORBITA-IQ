import asyncio
import logging
import os
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

CELESTRAK_BASE_URLS = [
    "https://celestrak.org/NORAD/elements/gp.php",
    "https://celestrak.com/NORAD/elements/gp.php",
]
CELESTRAK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

ACTIVE_TLE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "active_satellites.tle")


def lookup_local_bundled_tle(norad_id: int) -> str | None:
    """
    Looks up a satellite TLE from the local bundled active space catalog.
    """
    if not os.path.exists(ACTIVE_TLE_PATH):
        return None
    try:
        with open(ACTIVE_TLE_PATH, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        idx = 0
        while idx < len(lines):
            if idx + 2 < len(lines) and lines[idx + 1].startswith("1 ") and lines[idx + 2].startswith("2 "):
                line1 = lines[idx + 1]
                line2 = lines[idx + 2]
                name = lines[idx]
                try:
                    nid = int(line1[2:7])
                    if nid == norad_id:
                        return f"{name}\n{line1}\n{line2}"
                except ValueError:
                    pass
                idx += 3
            elif idx + 1 < len(lines) and lines[idx].startswith("1 ") and lines[idx + 1].startswith("2 "):
                line1 = lines[idx]
                line2 = lines[idx + 1]
                try:
                    nid = int(line1[2:7])
                    if nid == norad_id:
                        return f"OBJECT {nid}\n{line1}\n{line2}"
                except ValueError:
                    pass
                idx += 2
            else:
                idx += 1
    except Exception as exc:
        logger.warning(f"Error reading local bundled TLE dataset for NORAD {norad_id}: {exc}")
    return None


async def fetch_tle_by_norad_id(norad_id: int, max_retries: int = 2) -> str:
    """
    Fetches the latest Two-Line Element (TLE) set for a given NORAD ID from CelesTrak
    or falls back to the embedded active satellite dataset if CelesTrak is unreachable.
    """
    last_error = None
    timeout_config = httpx.Timeout(connect=8.0, read=15.0, write=8.0, pool=8.0)

    for base_url in CELESTRAK_BASE_URLS:
        url = f"{base_url}?CATNR={norad_id}&FORMAT=tle"
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(headers=CELESTRAK_HEADERS, timeout=timeout_config) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    text = response.text.strip()

                    if "No GP data found" in text or text == "":
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"No TLE data found for NORAD ID {norad_id} on CelesTrak."
                        )

                    lines = text.split("\n")
                    if len(lines) < 2:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Invalid TLE format received from CelesTrak."
                        )

                    return text

            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No TLE data found for NORAD ID {norad_id} on CelesTrak."
                    )
                last_error = exc
                await asyncio.sleep(1)
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(1)

    # If live endpoints failed or timed out, attempt local offline catalog lookup
    local_tle = lookup_local_bundled_tle(norad_id)
    if local_tle:
        logger.info(f"Resolved NORAD {norad_id} from local bundled catalog after network timeout.")
        return local_tle

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Failed to communicate with CelesTrak ({last_error}) and NORAD {norad_id} not in offline cache."
    )
