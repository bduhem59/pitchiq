import { useEffect, useState } from "react";
import { getPlayer } from "../api";

export function usePlayer(name, league = "Ligue_1") {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!name) return;

    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(null);

    getPlayer(name, league)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [name, league]);

  return { data, loading, error };
}
