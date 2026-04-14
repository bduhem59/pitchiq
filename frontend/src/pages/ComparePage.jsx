import { usePlayer }   from "../hooks/usePlayer";
import ErrorBoundary  from "../components/ErrorBoundary";
import StatCard       from "../components/StatCard";
import ShotMap        from "../components/ShotMap";
import _Plot          from "react-plotly.js";
const Plot = _Plot.default ?? _Plot;

// ── Constants ──────────────────────────────────────────────────────────────

const P1_COLOR = "#00d2ff";   // cyan
const P2_COLOR = "#ff8c00";   // orange

const RADAR_METRICS = ["xG_90", "npxG_90", "xA_90", "xGChain_90", "xGBuildup_90"];
const RADAR_LABELS  = ["xG/90", "npxG/90", "xA/90", "xGChain/90", "xGBuildup/90"];
const RADAR_MAX     = { xG_90: 0.9, npxG_90: 0.7, xA_90: 0.4, xGChain_90: 1.0, xGBuildup_90: 0.5 };

const ADV_METRICS = [
  { key: "xG_90",        label: "xG / 90",        tooltip: "Expected goals per 90 minutes based on shot quality" },
  { key: "npxG_90",      label: "npxG / 90",       tooltip: "Non-penalty xG — pure offensive threat excluding penalties" },
  { key: "xA_90",        label: "xA / 90",         tooltip: "Expected assists — quality of passes leading to shots" },
  { key: "xGChain_90",   label: "xGChain / 90",    tooltip: "xG from all offensive actions the player is involved in" },
  { key: "xGBuildup_90", label: "xGBuildup / 90",  tooltip: "Contribution to offensive build-up play before shots" },
];

const SEASON_KEYS = [
  { key: "games",   label: "Matches", fmt: (v) => v },
  { key: "minutes", label: "Minutes", fmt: (v) => Number(v).toLocaleString("en-US") },
  { key: "goals",   label: "Goals",   fmt: (v) => v },
  { key: "assists", label: "Assists", fmt: (v) => v },
  { key: "xG",      label: "xG",     fmt: (v) => Number(v).toFixed(1) },
  { key: "xA",      label: "xA",     fmt: (v) => Number(v).toFixed(1) },
];

// ── Sub-components ─────────────────────────────────────────────────────────

function PlayerCol({ data, color, fallbackName }) {
  const tm    = data?.transfermarkt || {};
  const us    = data?.understat     || {};
  const name  = (tm.full_name && tm.full_name !== "N/A") ? tm.full_name : (fallbackName || us.player_name || "—");
  const club  = tm.club && tm.club !== "N/A" ? tm.club : "—";
  const photo = data?.photo_data_uri;
  const avg   = data?.avg_percentile;
  const clubLogoDataUri = data?.club_logo_data_uri;

  return (
    <div className="flex flex-col items-center text-center">
      {photo ? (
        <img src={photo} alt={name}
             className="w-28 h-36 object-cover object-top rounded-2xl mb-4"
             style={{ border: `2px solid ${color}50` }} />
      ) : (
        <div className="w-28 h-36 rounded-2xl bg-surface border flex items-center justify-center text-5xl mb-4"
             style={{ borderColor: `${color}30` }}>
          👤
        </div>
      )}
      <h2 className="font-manrope font-black leading-tight mb-2"
          style={{ fontSize: "clamp(1.2rem, 2vw, 1.8rem)", letterSpacing: "-1px", color }}>
        {name}
      </h2>
      <div className="flex items-center gap-2 flex-wrap justify-center">
        {club !== "—" && (
          <span className="inline-flex items-center gap-1.5 badge">
            {clubLogoDataUri && (
              <img src={clubLogoDataUri} alt="" className="w-4 h-4 object-contain rounded-sm" />
            )}
            {club}
          </span>
        )}
        {avg != null && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold"
                style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}>
            {Math.round(avg)}th pct
          </span>
        )}
      </div>
    </div>
  );
}

function SeasonComparison({ us1, us2 }) {
  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
      {SEASON_KEYS.map(({ key, label, fmt }) => {
        const v1     = us1[key] ?? 0;
        const v2     = us2[key] ?? 0;
        const p1wins = Number(v1) > Number(v2);
        const p2wins = Number(v2) > Number(v1);
        return (
          <div key={key}
               className="flex flex-col items-center justify-center h-28 px-2 rounded-2xl
                          border border-[rgba(255,255,255,0.05)]"
               style={{ background: "#162030" }}>
            {/* P1 value */}
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ background: P1_COLOR, opacity: 0.8 }} />
              <span className="font-manrope font-black leading-none"
                    style={{ fontSize: "clamp(1.1rem,2vw,1.5rem)", letterSpacing: "-0.5px",
                             color: p1wins ? P1_COLOR : "#8899aa" }}>
                {fmt(v1)}
              </span>
            </div>
            {/* Separator + label */}
            <div className="flex items-center gap-2 my-1.5 w-full px-3">
              <div className="flex-1 h-px bg-[rgba(255,255,255,0.07)]" />
              <span className="text-[8px] text-muted/50 font-semibold uppercase tracking-[1.5px] shrink-0">
                {label}
              </span>
              <div className="flex-1 h-px bg-[rgba(255,255,255,0.07)]" />
            </div>
            {/* P2 value */}
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ background: P2_COLOR, opacity: 0.8 }} />
              <span className="font-manrope font-black leading-none"
                    style={{ fontSize: "clamp(1.1rem,2vw,1.5rem)", letterSpacing: "-0.5px",
                             color: p2wins ? P2_COLOR : "#8899aa" }}>
                {fmt(v2)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CompareRadar({ pct1, pct2, name1, name2 }) {
  if (!pct1 || !pct2) return (
    <div className="flex items-center justify-center h-48 text-muted text-sm">
      Radar unavailable — percentile data missing
    </div>
  );

  const toVals = (pct) => RADAR_METRICS.map((k) => Math.min((pct[k] ?? 0) / (RADAR_MAX[k] ?? 1), 1));
  const v1     = [...toVals(pct1), toVals(pct1)[0]];
  const v2     = [...toVals(pct2), toVals(pct2)[0]];
  const labels = [...RADAR_LABELS, RADAR_LABELS[0]];

  return (
    <Plot
      data={[
        {
          type: "scatterpolar", r: v1, theta: labels,
          fill: "toself", fillcolor: "rgba(0,210,255,0.15)",
          line: { color: P1_COLOR, width: 2 }, name: name1,
          hovertemplate: "%{theta}: %{r:.2f}<extra></extra>",
        },
        {
          type: "scatterpolar", r: v2, theta: labels,
          fill: "toself", fillcolor: "rgba(255,140,0,0.15)",
          line: { color: P2_COLOR, width: 2 }, name: name2,
          hovertemplate: "%{theta}: %{r:.2f}<extra></extra>",
        },
      ]}
      layout={{
        polar: {
          bgcolor: "transparent",
          radialaxis: {
            visible: true, range: [0, 1],
            showticklabels: false, showgrid: true,
            gridcolor: "rgba(255,255,255,0.06)", gridwidth: 1,
            linecolor: "transparent",
          },
          angularaxis: {
            tickfont: { color: "#bbc9cf", size: 10, family: "Inter" },
            linecolor: "rgba(255,255,255,0.08)",
            gridcolor: "rgba(255,255,255,0.06)",
          },
        },
        paper_bgcolor: "#0d1117",
        plot_bgcolor:  "transparent",
        legend: {
          font: { color: "#bbc9cf", size: 11, family: "Manrope" },
          bgcolor: "rgba(13,17,23,0.8)",
          bordercolor: "rgba(165,231,255,0.1)", borderwidth: 1,
          x: 0.5, xanchor: "center", y: -0.08, yanchor: "top",
        },
        margin: { t: 40, l: 40, r: 40, b: 40 },
        height: 460,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
    />
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function ComparePage({ p1, p1League, p2, p2League, onBack, onNavigate }) {
  const { data: d1, loading: l1, error: e1 } = usePlayer(p1, p1League);
  const { data: d2, loading: l2, error: e2 } = usePlayer(p2, p2League);

  const loading = l1 || l2;

  if (loading) return (
    <div className="flex items-center justify-center min-h-[calc(100vh-56px)]">
      <div className="flex flex-col items-center gap-4 text-muted">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading comparison…</span>
      </div>
    </div>
  );

  if (e1 || e2) return (
    <div className="flex items-center justify-center min-h-[calc(100vh-56px)] px-6">
      <div className="rounded-2xl border border-red-500/30 bg-red-950/30 p-8 max-w-md text-center">
        <div className="text-2xl mb-3">⚠️</div>
        <div className="text-text font-semibold mb-2">Could not load player data</div>
        <div className="text-muted text-sm">{(e1 || e2)?.message}</div>
      </div>
    </div>
  );

  const us1  = d1?.understat          || {};
  const us2  = d2?.understat          || {};
  const pct1 = d1?.percentile_record  || null;
  const pct2 = d2?.percentile_record  || null;
  const ctx1 = d1?.percentile_context || null;
  const ctx2 = d2?.percentile_context || null;

  const name1 = (d1?.transfermarkt?.full_name && d1.transfermarkt.full_name !== "N/A")
    ? d1.transfermarkt.full_name : (us1.player_name || p1);
  const name2 = (d2?.transfermarkt?.full_name && d2.transfermarkt.full_name !== "N/A")
    ? d2.transfermarkt.full_name : (us2.player_name || p2);

  const shots1 = us1.shot_coords || [];
  const shots2 = us2.shot_coords || [];

  return (
    <main className="max-w-[1420px] mx-auto px-6 pt-6 pb-16">

      {/* Back */}
      <button onClick={onBack}
              className="inline-flex items-center gap-2 mb-6 text-sm text-muted
                         hover:text-accent transition-colors cursor-pointer">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back
      </button>

      {/* ── 1. Header ──────────────────────────────────────────────────────── */}
      <div className="section-label mb-4">Comparison</div>
      <div className="grid grid-cols-2 gap-6 mb-8 pb-8 border-b border-[rgba(255,255,255,0.05)]">
        <ErrorBoundary>
          <PlayerCol data={d1} color={P1_COLOR} fallbackName={p1} />
        </ErrorBoundary>
        <ErrorBoundary>
          <PlayerCol data={d2} color={P2_COLOR} fallbackName={p2} />
        </ErrorBoundary>
      </div>

      {/* ── 2. Current Season ──────────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="section-label mb-4">Current Season</div>
        {/* Player name labels above */}
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-1">
          <div className="text-[10px] font-bold text-center truncate col-span-3 md:col-span-6">
            <span style={{ color: P1_COLOR }}>{name1}</span>
            <span className="text-muted/40 mx-2">vs</span>
            <span style={{ color: P2_COLOR }}>{name2}</span>
          </div>
        </div>
        <ErrorBoundary>
          <SeasonComparison us1={us1} us2={us2} />
        </ErrorBoundary>
      </div>

      {/* ── 3. Radar ───────────────────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="section-label mb-4">Radar Comparison</div>
        <div className="rounded-2xl overflow-hidden border border-[rgba(165,231,255,0.08)]
                        shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
             style={{ background: "#0d1117" }}>
          <ErrorBoundary>
            <CompareRadar pct1={pct1} pct2={pct2} name1={name1} name2={name2} />
          </ErrorBoundary>
        </div>
      </div>

      {/* ── 4. Advanced Stats — side-by-side per KPI ───────────────────────── */}
      <div className="mb-8">
        <div className="section-label mb-3">Advanced Stats / 90 min</div>
        {/* Column headers */}
        <div className="grid grid-cols-2 gap-4 mb-2">
          <div className="text-[10px] font-bold uppercase tracking-widest text-center"
               style={{ color: P1_COLOR }}>{name1}</div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-center"
               style={{ color: P2_COLOR }}>{name2}</div>
        </div>
        {/* 5 rows × 2 columns */}
        <div className="flex flex-col gap-3">
          {ADV_METRICS.map(({ key, label, tooltip }) => (
            <div key={key} className="grid grid-cols-2 gap-4">
              <ErrorBoundary>
                <StatCard
                  label={label}
                  value={pct1?.[key] ?? 0}
                  pct={pct1?.percentiles?.[key] ?? null}
                  rank={ctx1?.ranks?.[key] ?? null}
                  total={ctx1?.total ?? null}
                  tooltip={tooltip}
                />
              </ErrorBoundary>
              <ErrorBoundary>
                <StatCard
                  label={label}
                  value={pct2?.[key] ?? 0}
                  pct={pct2?.percentiles?.[key] ?? null}
                  rank={ctx2?.ranks?.[key] ?? null}
                  total={ctx2?.total ?? null}
                  tooltip={tooltip}
                />
              </ErrorBoundary>
            </div>
          ))}
        </div>
      </div>

      {/* ── 5. Shot Maps ───────────────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="section-label mb-4">Shot Maps</div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <div className="text-[10px] font-bold mb-2 uppercase tracking-widest"
                 style={{ color: P1_COLOR }}>{name1}</div>
            <div className="rounded-2xl overflow-hidden border border-[rgba(165,231,255,0.08)]
                            shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
                 style={{ background: "#0d1117" }}>
              <ErrorBoundary>
                <ShotMap
                  shotCoords={shots1}
                  playerName={name1}
                  nGoals={shots1.filter(s => s.result === "Goal").length}
                  nShots={shots1.length}
                />
              </ErrorBoundary>
            </div>
          </div>
          <div>
            <div className="text-[10px] font-bold mb-2 uppercase tracking-widest"
                 style={{ color: P2_COLOR }}>{name2}</div>
            <div className="rounded-2xl overflow-hidden border border-[rgba(165,231,255,0.08)]
                            shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
                 style={{ background: "#0d1117" }}>
              <ErrorBoundary>
                <ShotMap
                  shotCoords={shots2}
                  playerName={name2}
                  nGoals={shots2.filter(s => s.result === "Goal").length}
                  nShots={shots2.length}
                />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      </div>

      <hr className="border-[rgba(255,255,255,0.05)]" />
      <p className="text-center text-[11px] text-[#3c494e] mt-4 tracking-wide">
        Sources: Understat · Transfermarkt · 2025/26
      </p>
    </main>
  );
}
