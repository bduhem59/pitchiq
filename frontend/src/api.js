import axios from "axios";

const BASE = import.meta.env.VITE_API_URL;

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

/** 3 most statistically similar players (same position, all leagues). */
export const getSimilarPlayers = (name, league = "Ligue_1") =>
  api
    .get(`/player/${encodeURIComponent(name)}/similar`, { params: { league } })
    .then((r) => r.data);

/** URL for a player's proxied photo (use directly in <img src>). */
export const getPlayerPhotoUrl = (name) =>
  `${import.meta.env.VITE_API_URL}/player/${encodeURIComponent(name)}/photo`;

/** URL for a player's proxied club logo (use directly in <img src>). */
export const getClubLogoUrl = (name) =>
  `${import.meta.env.VITE_API_URL}/player/${encodeURIComponent(name)}/club-logo`;
