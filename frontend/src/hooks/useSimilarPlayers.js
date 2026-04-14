import { useState, useEffect } from "react";
import { getSimilarPlayers } from "../api";

export function useSimilarPlayers(playerName, league = "Ligue_1") {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!playerName) return;

    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(null);

    getSimilarPlayers(playerName, league)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err) => { if (!cancelled) setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [playerName, league]);

  return { data, loading, error };
}
