import axios from "axios";

const BASE = "http://127.0.0.1:8000";

export const api = axios.create({ baseURL: BASE });

/** All players across all leagues (or filtered by ?league=). */
export const getPlayersList = (league = null) =>
  api.get("/players/list", { params: league ? { league } : {} }).then((r) => r.data);

/** Full player card data. */
export const getPlayer = (name, league = "Ligue_1", season = "2025") =>
  api
    .get(`/player/${encodeURIComponent(name)}`, { params: { league, season } })
    .then((r) => r.data);

/** Per-position average /90 values for the radar reference polygon. */
export const getLeagueAverages = (league = "Ligue_1") =>
  api.get("/league/averages", { params: { league } }).then((r) => r.data);
