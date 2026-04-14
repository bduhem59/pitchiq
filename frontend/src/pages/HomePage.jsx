import SearchBar from "../components/SearchBar";
import { usePlayersList } from "../hooks/usePlayersList";
import { LEAGUES } from "../leagues";
import logo from "../assets/logo.svg";

export default function HomePage({ onNavigate }) {
  const { players, loading, error } = usePlayersList(null);

  const handleSearch = (name, league) => onNavigate("player", name, league);

  const nPlayers = players.length;

  return (
    <main className="flex flex-col items-center min-h-[calc(100vh-56px)] px-6 py-16">
      {/* Hero */}
      <div className="flex flex-col items-center gap-3 mb-12">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center
                        shadow-[0_4px_30px_rgba(0,210,255,0.3)] mb-2">
          <img src={logo} alt="PitchIQ" className="w-14 h-14" />
        </div>
        <h1 className="font-manrope font-black text-5xl leading-tight tracking-[-2px] m-0
                       bg-gradient-to-r from-text to-primary bg-clip-text text-transparent"
            style={{ WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          PitchIQ
        </h1>
        <p className="font-manrope text-[10px] text-muted font-bold tracking-[4px] uppercase m-0">
          Football Intelligence Platform
        </p>
        <p className="text-xs text-[#3c494e] mt-1 tracking-wide">
          {nPlayers > 0 ? `${nPlayers} players across 5 leagues` : "Loading…"} · Season 2025/26
        </p>
      </div>

      {/* Two-column layout */}
      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">

        {/* Left — Search */}
        <div className="glass-card p-7 flex flex-col">
          <div className="text-accent font-manrope font-black text-[11px] tracking-[2px] uppercase mb-3">
            Search a player
          </div>
          <p className="text-muted text-[13px] mb-5 leading-relaxed">
            Search across all 5 leagues to open any player's scouting report.
          </p>
          {loading && (
            <div className="text-muted text-xs text-center py-3">Loading player database…</div>
          )}
          {error && (
            <div className="text-red-400 text-xs mb-3">
              ⚠ Backend unreachable — start <code className="bg-surface px-1 rounded">uvicorn api:app</code>
            </div>
          )}
          {!loading && (
            <SearchBar players={players} onSelect={handleSearch} />
          )}
        </div>

        {/* Right — League grid */}
        <div className="glass-card p-7">
          <div className="text-accent font-manrope font-black text-[11px] tracking-[2px] uppercase mb-4">
            Explore by league
          </div>
          <div className="grid grid-cols-1 gap-2">
            {LEAGUES.map((l) => (
              <button
                key={l.code}
                onClick={() => onNavigate("explore", null, l.code)}
                className="flex items-center gap-3 px-4 py-3 rounded-xl text-left
                           border border-[rgba(165,231,255,0.08)] bg-[rgba(255,255,255,0.02)]
                           hover:bg-[rgba(0,210,255,0.06)] hover:border-accent/30
                           transition-all duration-200 active:scale-[.98] group"
              >
                <div className="w-8 h-8 rounded-md bg-white flex items-center justify-center shrink-0 p-1">
                  <img src={l.logo} alt={l.name}
                       className="w-full h-full object-contain"
                       onError={(e) => { e.target.parentElement.style.display = "none"; }} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-manrope font-black text-text text-sm leading-tight
                                  group-hover:text-primary transition-colors">
                    {l.name}
                  </div>
                  <div className="text-[10px] text-muted mt-0.5">{l.country}</div>
                </div>
                <svg className="w-4 h-4 text-muted/30 shrink-0 group-hover:text-accent/60 transition-colors"
                     fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            ))}
          </div>
        </div>

      </div>
    </main>
  );
}
