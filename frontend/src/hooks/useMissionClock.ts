import { useEffect, useState } from "react";

/** Ticking UTC clock for the mission-control topbar. */
export function useMissionClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return now;
}
