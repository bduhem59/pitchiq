const API = import.meta.env.VITE_API_URL;
const V   = "?v=2";

export const LEAGUES = [
  { code: "Ligue_1",    name: "Ligue 1",        flag: "🇫🇷", country: "France",  logo: `${API}/league/logo/Ligue_1${V}`    },
  { code: "EPL",        name: "Premier League",  flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", country: "England", logo: `${API}/league/logo/EPL${V}`         },
  { code: "La_Liga",    name: "La Liga",         flag: "🇪🇸", country: "Spain",   logo: `${API}/league/logo/La_Liga${V}`    },
  { code: "Bundesliga", name: "Bundesliga",      flag: "🇩🇪", country: "Germany", logo: `${API}/league/logo/Bundesliga${V}` },
  { code: "Serie_A",    name: "Serie A",         flag: "🇮🇹", country: "Italy",   logo: `${API}/league/logo/Serie_A${V}`   },
];

export const LEAGUE_MAP = Object.fromEntries(LEAGUES.map((l) => [l.code, l]));
