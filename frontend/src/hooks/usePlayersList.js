import { useEffect, useState } from "react";
import { getPlayersList } from "../api";

/** Pass league=null to load all leagues. */
export function usePlayersList(league = null) {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    setLoading(true);
    getPlayersList(league)
      .then(setPlayers)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [league]);

  return { players, loading, error };
}
