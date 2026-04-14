import { useEffect, useState } from "react";
import { getPlayerShots } from "../api";

export function usePlayerShots(name, league = "Ligue_1", season = "2025") {
  const [shots,   setShots]   = useState([]);
  const [loading, setLoading] = useState(!!name);
  const [error,   setError]   = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!name) return;

    let cancelled = false;
    setLoading(true);
    setShots([]);
    setError(null);

    getPlayerShots(name, league, season)
      .then((res) => { if (!cancelled) setShots(res.shot_coords ?? []); })
      .catch((err) => { if (!cancelled) setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [name, league, season, attempt]);

  const retry = () => setAttempt((n) => n + 1);

  return { shots, loading, error, retry };
}
