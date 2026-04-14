import { useState, useRef, useEffect } from "react";
import logo from "../assets/logo.svg";
import { LEAGUE_MAP } from "../leagues";

export default function Navbar({ view, onNavigate, players, onSearch, currentLeague }) {
  const leagueInfo = LEAGUE_MAP[currentLeague] || null;
  return (
    <header className="sticky top-0 z-40 w-full border-b border-[rgba(255,255,255,0.05)]"
      style={{ background: "rgba(9,20,35,0.92)", backdropFilter: "blur(16px)" }}>
      <div className="max-w-[1420px] mx-auto px-6 h-14 flex items-center gap-6">
        {/* Back button */}
        {view !== "home" && (
          <button
            onClick={() => onNavigate("home")}
            className="flex items-center justify-center w-9 h-9 rounded-full
                       border border-[rgba(255,255,255,0.1)] text-muted
                       hover:text-text hover:border-accent/40 transition-all shrink-0"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        )}

        {/* Logo */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center
                          shadow-[0_2px_12px_rgba(0,210,255,0.3)]">
            <img src={logo} alt="PitchIQ" className="w-7 h-7" />
          </div>
          <div>
            <div className="font-manrope font-black italic text-primary text-sm tracking-wide leading-none">
              PitchIQ
            </div>
            <div className="flex items-center gap-1 text-[9px] text-muted/60 tracking-widest uppercase leading-none mt-0.5">
              {leagueInfo ? (
                <>
                  <span className="inline-flex w-3.5 h-3.5 rounded bg-white items-center justify-center p-px shrink-0">
                    <img src={leagueInfo.logo} alt={leagueInfo.name}
                         className="w-full h-full object-contain"
                         onError={(e) => { e.target.parentElement.style.display = "none"; }} />
                  </span>
                  {leagueInfo.name}
                </>
              ) : "Football Intelligence"}
            </div>
          </div>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Search — masquée sur la landing page */}
        {players && onSearch && view !== "home" && (
          <div className="w-72">
            <SearchBarInline players={players} onSelect={onSearch} />
          </div>
        )}
      </div>
    </header>
  );
}

/** Compact inline search for the navbar */
function SearchBarInline({ players, onSelect }) {
  const [query,   setQuery]   = useState("");
  const [open,    setOpen]    = useState(false);
  const [focused, setFocused] = useState(false);
  const ref                   = useRef(null);

  const filtered =
    query.trim().length < 1
      ? []
      : players
          .filter((p) =>
            p.player_name.toLowerCase().includes(query.toLowerCase())
          )
          .slice(0, 6);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div className={`flex items-center gap-2 px-3 py-2 rounded-[10px] border transition-all
                      bg-[rgba(255,255,255,0.08)]
                      ${focused ? "border-[rgba(0,210,255,0.6)] shadow-[0_0_0_2px_rgba(0,210,255,0.1)]" : "border-[rgba(165,231,255,0.25)]"}`}>
        <svg className="w-3.5 h-3.5 text-muted/60 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => { setOpen(true); setFocused(true); }}
          onBlur={() => setFocused(false)}
          placeholder="Search for a player…"
          className="flex-1 bg-transparent text-text text-xs outline-none placeholder:text-[#8899aa] font-manrope"
        />
      </div>
      {open && filtered.length > 0 && (
        <ul className="absolute right-0 mt-1 w-full rounded-xl border border-[rgba(255,255,255,0.08)]
                       bg-surface shadow-[0_8px_32px_rgba(0,0,0,0.5)] overflow-hidden z-50">
          {filtered.map((p) => (
            <li
              key={`${p.player_name}-${p.league}`}
              onMouseDown={() => { setQuery(p.player_name); setOpen(false); onSelect(p.player_name, p.league || "Ligue_1"); }}
              className="flex items-center justify-between px-3 py-2.5 cursor-pointer
                         hover:bg-[rgba(0,210,255,0.07)] transition-colors"
            >
              <span className="text-xs font-semibold text-text">{p.player_name}</span>
              <span className="text-[10px] text-muted">{p.team}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
