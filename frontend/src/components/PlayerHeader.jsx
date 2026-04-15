import { useState, useRef, useEffect } from "react";

const POSITION_MAP = {
  "Attack - Centre-Forward":       "Centre Forward",
  "Attack - Left Winger":          "Left Winger",
  "Attack - Right Winger":         "Right Winger",
  "Attack - Second Striker":       "Second Striker",
  "Midfield - Central Midfield":   "Central Midfielder",
  "Midfield - Attacking Midfield": "Attacking Midfielder",
  "Midfield - Defensive Midfield": "Defensive Midfielder",
  "Midfield - Right Midfield":     "Right Midfielder",
  "Midfield - Left Midfield":      "Left Midfielder",
  "Midfield - Right Wing":         "Right Winger",
  "Midfield - Left Wing":          "Left Winger",
  "Defence - Centre-Back":         "Centre Back",
  "Defence - Left-Back":           "Left Back",
  "Defence - Right-Back":          "Right Back",
  "Defence - Left Wing-Back":      "Left Wing Back",
  "Defence - Right Wing-Back":     "Right Wing Back",
  "Defence - Sweeper":             "Sweeper",
  "Goalkeeper":                    "Goalkeeper",
};

const NAT_FLAGS = {
  France:"🇫🇷", Spain:"🇪🇸", Germany:"🇩🇪", Portugal:"🇵🇹",
  Italy:"🇮🇹", England:"🏴󠁧󠁢󠁥󠁮󠁧󠁿", Netherlands:"🇳🇱", Belgium:"🇧🇪",
  Switzerland:"🇨🇭", Austria:"🇦🇹", Croatia:"🇭🇷", Serbia:"🇷🇸",
  Poland:"🇵🇱", Denmark:"🇩🇰", Sweden:"🇸🇪", Norway:"🇳🇴",
  Scotland:"🏴󠁧󠁢󠁳󠁣󠁴󠁿", Turkey:"🇹🇷", Greece:"🇬🇷", Romania:"🇷🇴",
  Ukraine:"🇺🇦", Georgia:"🇬🇪", Albania:"🇦🇱", Kosovo:"🇽🇰",
  Brazil:"🇧🇷", Argentina:"🇦🇷", Colombia:"🇨🇴", Uruguay:"🇺🇾",
  Chile:"🇨🇱", Mexico:"🇲🇽", "United States":"🇺🇸", Canada:"🇨🇦",
  Morocco:"🇲🇦", Algeria:"🇩🇿", Tunisia:"🇹🇳", Senegal:"🇸🇳",
  "Ivory Coast":"🇨🇮", Ghana:"🇬🇭", Nigeria:"🇳🇬", Cameroon:"🇨🇲",
  Mali:"🇲🇱", Guinea:"🇬🇳", "DR Congo":"🇨🇩", Congo:"🇨🇬",
  Gabon:"🇬🇦", Egypt:"🇪🇬", "Burkina Faso":"🇧🇫",
  "Guinea-Bissau":"🇬🇼", Comoros:"🇰🇲", "Cape Verde":"🇨🇻",
  Gambia:"🇬🇲", Japan:"🇯🇵", "South Korea":"🇰🇷", Australia:"🇦🇺",
};

function natWithFlag(nat) {
  if (!nat || nat === "N/A") return nat;
  if (NAT_FLAGS[nat]) return `${NAT_FLAGS[nat]} ${nat}`;
  const parts = nat.split(" ");
  let result = []; let i = 0;
  while (i < parts.length) {
    const two = parts.slice(i, i + 2).join(" ");
    if (i + 1 < parts.length && NAT_FLAGS[two]) {
      result.push(`${NAT_FLAGS[two]} ${two}`); i += 2;
    } else {
      const f = NAT_FLAGS[parts[i]] || "";
      result.push(f ? `${f} ${parts[i]}` : parts[i]); i++;
    }
  }
  return result.join(" / ");
}

function Badge({ children }) {
  return <span className="badge">{children}</span>;
}

export default function PlayerHeader({ transfermarkt, photoDataUri, clubLogoDataUri, avgPercentile, tmProfileUrl, minutes, fallbackName, players, onCompare, currentLeague }) {
  const tm = transfermarkt || {};

  const rawName = tm.full_name;
  const name    = (rawName && rawName !== "N/A") ? rawName : (fallbackName || "—");
  const _v      = (v) => (v && v !== "N/A") ? v : null;
  const club    = _v(tm.club)            || "—";
  const nat     = _v(tm.nationality)     || "—";
  const posRaw  = _v(tm.position)        || "—";
  const pos     = POSITION_MAP[posRaw]   || posRaw;
  const age     = _v(tm.dob_age)         || "—";
  const val     = _v(tm.market_value)    || "—";
  const ctr     = _v(tm.contract_expiry) || "—";
  const profUrl = tmProfileUrl || tm.profile_url || "";

  const valClean = val !== "N/A" && val !== "—"
    ? val.replace(/^€\s*/, "").trim().replace(/\bm\b/, "M") + " €"
    : null;

  const isElite = avgPercentile != null && avgPercentile >= 85 && (minutes ?? 0) >= 300;

  // ── Compare search state ──────────────────────────────────────────────────
  const [compareOpen,  setCompareOpen]  = useState(false);
  const [compareQuery, setCompareQuery] = useState("");
  const compareRef = useRef(null);

  // Use the Understat name (fallbackName) for API calls — TM name may differ in accents/format
  const understatName = fallbackName || name;

  const compareFiltered = compareQuery.trim().length < 1 ? [] :
    (players || [])
      .filter(p => p.player_name.toLowerCase().includes(compareQuery.toLowerCase())
               && p.player_name !== understatName)
      .slice(0, 8);

  useEffect(() => {
    const h = (e) => { if (compareRef.current && !compareRef.current.contains(e.target)) setCompareOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const handleCompareSelect = (p) => {
    setCompareOpen(false);
    setCompareQuery("");
    onCompare?.(understatName, currentLeague, p.player_name, p.league || "Ligue_1");
  };

  return (
    <section className="mt-2 mb-6 pb-6 border-b border-[rgba(255,255,255,0.05)]">
      <div className="font-manrope font-black text-accent text-[11px] uppercase tracking-[2px] mb-4">
        Player Profile
      </div>
      <div className="flex gap-7 items-start">
        {/* Photo */}
        <div className="shrink-0">
          {photoDataUri ? (
            <img src={photoDataUri} alt={name}
                 className="w-32 h-44 object-cover object-top rounded-2xl block" />
          ) : (
            <div className="w-32 h-44 rounded-2xl bg-surface border border-[rgba(255,255,255,0.05)]
                            flex items-center justify-center text-5xl text-[#3c494e]">
              👤
            </div>
          )}
          {profUrl && (
            <a href={profUrl} target="_blank" rel="noreferrer"
               className="block mt-2 text-[10px] text-muted hover:text-accent transition-colors
                          text-center no-underline tracking-wide">
              ↗ Transfermarkt
            </a>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0 pt-1">
          {/* Name + Compare button */}
          <div className="flex items-start justify-between gap-4 mb-5">
            <h1 className="font-manrope font-black text-text leading-tight m-0"
                style={{ fontSize: "clamp(1.8rem, 3vw, 2.8rem)", letterSpacing: "-1.5px" }}>
              {name}
            </h1>
            {onCompare && (
              <div ref={compareRef} className="relative shrink-0 mt-1">
                <button
                  onClick={() => setCompareOpen((o) => !o)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full
                             text-[11px] font-bold uppercase tracking-[1.5px] transition-all
                             border border-[rgba(0,210,255,0.35)] bg-[rgba(0,210,255,0.07)]
                             text-accent hover:border-accent hover:bg-[rgba(0,210,255,0.14)]
                             hover:shadow-[0_0_12px_rgba(0,210,255,0.2)] cursor-pointer">
                  ⇄ Compare
                </button>
                {compareOpen && (
                  <div className="absolute right-0 top-full mt-2 w-72 z-50
                                  rounded-xl border border-[rgba(165,231,255,0.2)]
                                  bg-[#0d1825] shadow-[0_8px_32px_rgba(0,0,0,0.6)] overflow-hidden">
                    <div className="p-2 border-b border-[rgba(255,255,255,0.06)]">
                      <input
                        autoFocus
                        type="text"
                        value={compareQuery}
                        onChange={(e) => setCompareQuery(e.target.value)}
                        placeholder="Search a player to compare…"
                        className="w-full bg-transparent text-text text-sm outline-none
                                   placeholder:text-[#8899aa] font-manrope px-2 py-1"
                      />
                    </div>
                    {compareFiltered.length > 0 ? (
                      <ul>
                        {compareFiltered.map((p) => (
                          <li key={`${p.player_name}-${p.league}`}
                              onMouseDown={() => handleCompareSelect(p)}
                              className="flex items-center justify-between px-4 py-2.5 cursor-pointer
                                         hover:bg-[rgba(0,210,255,0.07)] transition-colors">
                            <div>
                              <div className="text-sm font-semibold text-text font-manrope">
                                {p.player_name}
                              </div>
                              <div className="text-[10px] text-muted/60">{p.team}</div>
                            </div>
                            {p.avg_percentile != null && (
                              <span className="text-xs font-bold px-2 py-0.5 rounded-full shrink-0"
                                    style={{
                                      background: p.avg_percentile >= 75 ? "rgba(0,210,255,0.15)" : "rgba(255,255,255,0.05)",
                                      color:      p.avg_percentile >= 75 ? "#00d2ff" : "#bbc9cf",
                                    }}>
                                {Math.round(p.avg_percentile)}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    ) : compareQuery.trim().length > 0 ? (
                      <div className="px-4 py-3 text-[11px] text-muted/50">No player found</div>
                    ) : (
                      <div className="px-4 py-3 text-[11px] text-muted/50">Type a name to search…</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            {club && club !== "—" && <Badge>{club}</Badge>}
            {nat  && nat  !== "—" && <Badge>{natWithFlag(nat)}</Badge>}
            {pos  && pos  !== "—" && <Badge>{pos}</Badge>}
            {age  && age  !== "—" && <Badge>{age}</Badge>}
            {valClean && (
              <span className="inline-flex items-center gap-[5px] px-3 py-1 rounded-full
                               text-[11px] font-bold uppercase tracking-[1.5px]"
                    style={{
                      background: "rgba(0,210,255,0.15)",
                      border:     "1px solid rgba(0,210,255,0.3)",
                      color:      "#00d2ff",
                    }}>
                {valClean}
              </span>
            )}
            {ctr  && ctr  !== "—" && ctr  !== "N/A" && <Badge>{ctr}</Badge>}
            {isElite && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-[10px]
                               font-black uppercase tracking-widest text-[#003543]
                               shadow-[0_0_16px_rgba(0,210,255,0.3)]"
                    style={{ background: "#00d2ff" }}>
                ★ ELITE RANK
              </span>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
