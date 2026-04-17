import { useState, useMemo } from "react";
import { usePlayersList } from "../hooks/usePlayersList";
import { LEAGUE_MAP } from "../leagues";

const PAGE_SIZE = 25;

const POS_OPTIONS = ["All", "Forward", "Midfielder", "Defender"];
const POS_LABEL   = { All: "Position", Forward: "Forward", Midfielder: "Midfielder", Defender: "Defender" };

function pctColor(v) {
  if (v == null) return "#3c4a5a";
  if (v >= 85)   return "#00d2ff";
  if (v >= 67)   return "#47d6ff";
  if (v >= 33)   return "#ffaa00";
  return "#ff4444";
}

const COLUMNS = [
  { label: "#",            k: null,             numeric: false, fixed: true },
  { label: "Player",       k: "player_name",    numeric: false },
  { label: "Club",         k: "team",           numeric: false },
  { label: "Position",     k: "position_group", numeric: false },
  { label: "Min",          k: "minutes",        numeric: true },
  { label: "Goals",        k: "goals",          numeric: true },
  { label: "Assists",      k: "assists",        numeric: true },
  { label: "xG/90",        k: "xG_90",          numeric: true,  tooltip: "Expected goals per 90 minutes based on shot quality" },
  { label: "npxG/90",      k: "npxG_90",        numeric: true,  tooltip: "Non-penalty xG — pure offensive threat excluding penalties" },
  { label: "xA/90",        k: "xA_90",          numeric: true,  tooltip: "Expected assists — quality of passes leading to shots" },
  { label: "xGChain/90",   k: "xGChain_90",     numeric: true,  tooltip: "xG from all offensive actions the player is involved in" },
  { label: "xGBuildup/90", k: "xGBuildup_90",   numeric: true,  tooltip: "Contribution to offensive build-up play before shots" },
  { label: "Avg Pct",      k: "avg_percentile", numeric: true },
];

const filterInputStyle = {
  background:   "rgba(255,255,255,0.06)",
  border:       "1px solid rgba(165,231,255,0.15)",
  borderRadius: 10,
  color:        "#d9e3f8",
  fontFamily:   "Manrope, sans-serif",
  fontSize:     13,
  padding:      "10px 14px",
  boxShadow:    "none",
};

const filterFocusStyle = {
  ...filterInputStyle,
  border:    "1px solid rgba(0,210,255,0.4)",
  boxShadow: "0 0 0 2px rgba(0,210,255,0.08)",
};

function ChevronIcon() {
  return (
    <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
      <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
        <path d="M1 1l4 4 4-4" stroke="rgba(0,210,255,0.6)" strokeWidth="1.5"
              strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function ColTooltip({ text }) {
  return (
    <span className="group/tip relative inline-flex shrink-0" onClick={(e) => e.stopPropagation()}>
      <span className="inline-flex items-center justify-center rounded-full shrink-0
                       border border-[rgba(165,231,255,0.4)] bg-[rgba(0,210,255,0.1)]
                       cursor-default select-none
                       hover:border-[#00d2ff] hover:shadow-[0_0_4px_rgba(0,210,255,0.3)]
                       transition-all duration-150"
           style={{ width: 14, height: 14 }}>
        <svg width="4" height="8" viewBox="0 0 4 8" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="2" cy="1" r="1" fill="rgba(165,231,255,0.8)" />
          <rect x="1" y="3" width="2" height="5" rx="1" fill="rgba(165,231,255,0.8)" />
        </svg>
      </span>
      <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1.5 w-44 p-2.5 rounded-xl
                      bg-[#0a1623] border border-[rgba(165,231,255,0.12)]
                      text-[9px] text-muted leading-[1.5] whitespace-normal
                      opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150
                      pointer-events-none z-50 shadow-[0_8px_24px_rgba(0,0,0,0.6)]
                      font-normal normal-case tracking-normal">
        {text}
      </div>
    </span>
  );
}

export default function ExplorePage({ onNavigate, league = "Ligue_1" }) {
  const leagueInfo = LEAGUE_MAP[league] || { name: league, flag: "" };
  const { players, loading } = usePlayersList(league);
  const [posFilter,  setPosFilter]  = useState("All");
  const [clubFilter, setClubFilter] = useState("All clubs");
  const [query,      setQuery]      = useState("");
  const [sortKey,    setSortKey]    = useState("avg_percentile");
  const [sortDir,    setSortDir]    = useState(-1); // -1 = desc
  const [page,       setPage]       = useState(1);

  const clubs = useMemo(() => {
    const s = new Set(players.map((p) => p.team).filter(Boolean));
    return ["All clubs", ...Array.from(s).sort()];
  }, [players]);

  const filtered = useMemo(() => {
    let rows = [...players];
    if (posFilter !== "All")        rows = rows.filter((p) => p.position_group === posFilter);
    if (clubFilter !== "All clubs") rows = rows.filter((p) => p.team === clubFilter);
    if (query.trim())               rows = rows.filter((p) =>
      p.player_name.toLowerCase().includes(query.toLowerCase()));
    rows.sort((a, b) => {
      const av = a[sortKey] ?? -1;
      const bv = b[sortKey] ?? -1;
      return typeof av === "string"
        ? av.localeCompare(bv) * sortDir
        : (av - bv) * sortDir;
    });
    return rows;
  }, [players, posFilter, clubFilter, query, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage   = Math.min(page, totalPages);
  const pageRows   = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const toggleSort = (key) => {
    if (!key) return;
    if (sortKey === key) setSortDir((d) => -d);
    else { setSortKey(key); setSortDir(-1); }
    setPage(1);
  };

  const handleFilter = (setter) => (e) => { setter(e.target.value); setPage(1); };

  return (
    <main className="max-w-[1420px] mx-auto px-6 pt-6 pb-16">
      <div className="section-label mb-5">
        Explore {leagueInfo.name} 2025/26
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-5">
        <input
          type="text" value={query} onChange={handleFilter(setQuery)}
          placeholder="Filter by name…"
          className="outline-none transition-all w-48"
          style={filterInputStyle}
          onFocus={e  => Object.assign(e.target.style, filterFocusStyle)}
          onBlur={e   => Object.assign(e.target.style, filterInputStyle)}
        />
        <div className="relative">
          <select value={posFilter} onChange={handleFilter(setPosFilter)}
            className="outline-none cursor-pointer appearance-none pr-8 transition-all"
            style={{ ...filterInputStyle, colorScheme: "dark" }}
            onFocus={e => Object.assign(e.target.style, { ...filterFocusStyle, colorScheme: "dark" })}
            onBlur={e  => Object.assign(e.target.style, { ...filterInputStyle, colorScheme: "dark" })}>
            {POS_OPTIONS.map((p) => (
              <option key={p} value={p} style={{ background: "#162030", color: "#d9e3f8" }}>
                {POS_LABEL[p] || p}
              </option>
            ))}
          </select>
          <ChevronIcon />
        </div>
        <div className="relative">
          <select value={clubFilter} onChange={handleFilter(setClubFilter)}
            className="outline-none cursor-pointer appearance-none pr-8 transition-all max-w-[200px]"
            style={{ ...filterInputStyle, colorScheme: "dark" }}
            onFocus={e => Object.assign(e.target.style, { ...filterFocusStyle, colorScheme: "dark" })}
            onBlur={e  => Object.assign(e.target.style, { ...filterInputStyle, colorScheme: "dark" })}>
            {clubs.map((c) => (
              <option key={c} value={c} style={{ background: "#162030", color: "#d9e3f8" }}>
                {c}
              </option>
            ))}
          </select>
          <ChevronIcon />
        </div>
        <span className="ml-auto text-xs text-muted self-center">{filtered.length} players</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-muted text-sm text-center py-12">Loading…</div>
      ) : (
        <>
          <div className="rounded-2xl border border-[rgba(255,255,255,0.05)] overflow-hidden"
               style={{ background: "#162030" }}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-[rgba(255,255,255,0.06)]">
                  <tr>
                    {COLUMNS.map(({ label, k, tooltip }) => (
                      <th
                        key={label}
                        onClick={() => toggleSort(k)}
                        className={`px-3 py-3 text-[10px] font-bold uppercase tracking-widest
                                    select-none whitespace-nowrap text-left relative
                                    ${k ? "cursor-pointer hover:text-accent transition-colors" : ""}
                                    ${sortKey === k ? "text-accent" : "text-muted"}`}
                      >
                        <span className="inline-flex items-center gap-1">
                          {label}
                          {sortKey === k && <span className="ml-1">{sortDir === -1 ? "↓" : "↑"}</span>}
                          {tooltip && <ColTooltip text={tooltip} />}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((p, i) => (
                    <tr key={p.player_name}
                        onClick={() => onNavigate("player", p.player_name, p.league)}
                        className="border-b border-[rgba(255,255,255,0.03)] cursor-pointer
                                   hover:bg-[rgba(0,210,255,0.05)] transition-colors">
                      {/* Row number */}
                      <td className="px-3 py-2.5 text-muted/40 text-xs tabular-nums">
                        {(safePage - 1) * PAGE_SIZE + i + 1}
                      </td>
                      {/* Player */}
                      <td className="px-3 py-2.5 font-semibold text-text whitespace-nowrap">
                        {p.player_name}
                      </td>
                      {/* Club */}
                      <td className="px-3 py-2.5 text-muted whitespace-nowrap">{p.team}</td>
                      {/* Position */}
                      <td className="px-3 py-2.5 text-muted">
                        {POS_LABEL[p.position_group] || p.position_group}
                      </td>
                      {/* Min */}
                      <td className="px-3 py-2.5 text-muted tabular-nums text-right">{p.minutes?.toLocaleString("en-US")}</td>
                      {/* Goals */}
                      <td className="px-3 py-2.5 tabular-nums text-right text-text">{p.goals}</td>
                      {/* Assists */}
                      <td className="px-3 py-2.5 tabular-nums text-right text-text">{p.assists}</td>
                      {/* xG/90 */}
                      <td className="px-3 py-2.5 tabular-nums text-right text-muted">{p.xG_90?.toFixed(2)}</td>
                      {/* npxG/90 */}
                      <td className="px-3 py-2.5 tabular-nums text-right text-muted">{p.npxG_90?.toFixed(2)}</td>
                      {/* xA/90 */}
                      <td className="px-3 py-2.5 tabular-nums text-right text-muted">{p.xA_90?.toFixed(2)}</td>
                      {/* xGChain/90 */}
                      <td className="px-3 py-2.5 tabular-nums text-right text-muted">{p.xGChain_90?.toFixed(2)}</td>
                      {/* xGBuildup/90 */}
                      <td className="px-3 py-2.5 tabular-nums text-right text-muted">{p.xGBuildup_90?.toFixed(2)}</td>
                      {/* Avg Pct */}
                      <td className="px-3 py-2.5">
                        {p.avg_percentile != null ? (
                          <div className="flex items-center gap-2 justify-end">
                            <div className="w-14 h-1.5 rounded-full bg-[rgba(255,255,255,0.07)] shrink-0">
                              <div className="h-full rounded-full"
                                   style={{
                                     width: `${p.avg_percentile}%`,
                                     background: pctColor(p.avg_percentile),
                                   }} />
                            </div>
                            <span className="text-xs font-bold tabular-nums"
                                  style={{ color: pctColor(p.avg_percentile) }}>
                              {Math.round(p.avg_percentile)}
                            </span>
                          </div>
                        ) : <span className="text-muted/40 float-right">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <button
                disabled={safePage <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-4 py-2 rounded-xl border border-[rgba(255,255,255,0.08)] text-sm text-muted
                           hover:text-text hover:border-accent/40 transition-colors
                           disabled:opacity-30 disabled:cursor-not-allowed"
              >
                ← Previous
              </button>
              <span className="text-xs text-muted">
                Page {safePage} / {totalPages}
                <span className="ml-3 text-muted/50">
                  ({(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, filtered.length)} of {filtered.length})
                </span>
              </span>
              <button
                disabled={safePage >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="px-4 py-2 rounded-xl border border-[rgba(255,255,255,0.08)] text-sm text-muted
                           hover:text-text hover:border-accent/40 transition-colors
                           disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}
