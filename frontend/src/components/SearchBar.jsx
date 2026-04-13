import { useState, useRef, useEffect } from "react";
import { LEAGUE_MAP } from "../leagues";

const POS_LABEL = {
  attaquants:   "Forward",
  milieux:      "Midfielder",
  "défenseurs": "Defender",
};

export default function SearchBar({ players, onSelect, placeholder = "Search for a player…" }) {
  const [query, setQuery]     = useState("");
  const [open, setOpen]       = useState(false);
  const [focused, setFocused] = useState(false);
  const containerRef          = useRef(null);

  const filtered =
    query.trim().length < 1
      ? []
      : players
          .filter((p) => p.player_name.toLowerCase().includes(query.toLowerCase()))
          .slice(0, 8);

  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSelect = (p) => {
    setQuery(p.player_name);
    setOpen(false);
    onSelect(p.player_name, p.league || "Ligue_1");
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <div
        className={`flex items-center gap-3 px-4 py-3 rounded-[10px] border transition-all
          bg-[rgba(255,255,255,0.08)]
          ${focused
            ? "border-[rgba(0,210,255,0.6)] shadow-[0_0_0_2px_rgba(0,210,255,0.1)]"
            : "border-[rgba(165,231,255,0.25)]"
          }`}
      >
        <svg className="w-4 h-4 text-muted shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => { setFocused(true); setOpen(true); }}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-text text-sm outline-none placeholder:text-[#8899aa]
                     font-manrope"
        />
        {query && (
          <button
            onClick={() => { setQuery(""); setOpen(false); }}
            className="text-muted hover:text-text transition-colors text-lg leading-none"
          >
            ×
          </button>
        )}
      </div>

      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full rounded-xl border border-[rgba(255,255,255,0.08)]
                       bg-surface shadow-[0_8px_32px_rgba(0,0,0,0.5)] overflow-hidden">
          {filtered.map((p) => {
            const leagueInfo = LEAGUE_MAP[p.league] || null;
            return (
              <li
                key={`${p.player_name}-${p.league}`}
                onMouseDown={() => handleSelect(p)}
                className="flex items-center justify-between px-4 py-3 cursor-pointer
                           hover:bg-[rgba(0,210,255,0.07)] transition-colors"
              >
                <div>
                  <div className="text-sm font-semibold text-text font-inter">
                    {p.player_name}
                    {p.team && (
                      <span className="font-normal text-muted"> — {p.team}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    {leagueInfo && (
                      <span className="text-[10px] text-muted/60">
                        {leagueInfo.name}
                      </span>
                    )}
                    {p.position_group && (
                      <span className="text-[10px] text-muted/40">
                        · {POS_LABEL[p.position_group] || p.position_group}
                      </span>
                    )}
                  </div>
                </div>
                {p.avg_percentile != null && (
                  <span
                    className="text-xs font-bold px-2 py-0.5 rounded-full shrink-0"
                    style={{
                      background: p.avg_percentile >= 75 ? "rgba(0,210,255,0.15)" : "rgba(255,255,255,0.05)",
                      color:      p.avg_percentile >= 75 ? "#00d2ff" : "#bbc9cf",
                    }}
                  >
                    {Math.round(p.avg_percentile)}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
