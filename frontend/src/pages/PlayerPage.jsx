import { useState, useEffect } from "react";
import { usePlayer }           from "../hooks/usePlayer";
import { useSimilarPlayers }   from "../hooks/useSimilarPlayers";
import { getLeagueAverages, getPlayerPhotoUrl, getClubLogoUrl } from "../api";
import ErrorBoundary           from "../components/ErrorBoundary";
import PlayerHeader            from "../components/PlayerHeader";
import SeasonStats             from "../components/SeasonStats";
import StatCard                from "../components/StatCard";
import ShotMap                 from "../components/ShotMap";
import RadarChart              from "../components/RadarChart";
import ScoutAnalysis           from "../components/ScoutAnalysis";
import SimilarPlayers          from "../components/SimilarPlayers";

const METRICS = [
  { key: "xG_90",        label: "xG / 90",        tooltip: "Expected goals per 90 minutes based on shot quality" },
  { key: "npxG_90",      label: "npxG / 90",       tooltip: "Non-penalty xG — pure offensive threat excluding penalties" },
  { key: "xA_90",        label: "xA / 90",         tooltip: "Expected assists — quality of passes leading to shots" },
  { key: "xGChain_90",   label: "xGChain / 90",    tooltip: "xG from all offensive actions the player is involved in" },
  { key: "xGBuildup_90", label: "xGBuildup / 90",  tooltip: "Contribution to offensive build-up play before shots" },
];

const POS_SINGULAR = {
  attaquants:  "Forward",
  milieux:     "Midfielder",
  "d\u00e9fenseurs": "Defender",
};

// ── Section wrapper with individual error boundary ─────────────────────────
function Section({ children }) {
  return (
    <ErrorBoundary>
      <div className="mb-8">{children}</div>
    </ErrorBoundary>
  );
}

export default function PlayerPage({ playerName, league = "Ligue_1", players, onCompare, onNavigate }) {
  const { data, loading, error } = usePlayer(playerName, league);
  const [leagueAvgs, setLeagueAvgs] = useState(null);
  const { data: similarData, loading: similarLoading, error: similarError } =
    useSimilarPlayers(playerName, league);

  useEffect(() => {
    getLeagueAverages(league).then(setLeagueAvgs).catch(() => {});
  }, [league]);

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) return (
    <div className="flex items-center justify-center min-h-[calc(100vh-56px)]">
      <div className="flex flex-col items-center gap-4 text-muted">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading {playerName}…</span>
      </div>
    </div>
  );

  // ── API error ─────────────────────────────────────────────────────────────
  if (error) return (
    <div className="flex items-center justify-center min-h-[calc(100vh-56px)] px-6">
      <div className="rounded-2xl border border-red-500/30 bg-red-950/30 p-8 max-w-md text-center">
        <div className="text-2xl mb-3">⚠️</div>
        <div className="text-text font-semibold mb-2">Player not found</div>
        <div className="text-muted text-sm">
          {error?.response?.data?.detail || error?.message || "Unknown error"}
        </div>
        <div className="text-[11px] text-muted/50 mt-3">
          Make sure <code className="bg-surface px-1 rounded">uvicorn api:app</code> is running
          on port 8000.
        </div>
      </div>
    </div>
  );

  if (!data) return null;

  // ── Destructure API response ───────────────────────────────────────────────
  const us    = data.understat          ?? {};
  const tm    = data.transfermarkt      ?? null;
  const pct   = data.percentile_record  ?? null;
  const ctx   = data.percentile_context ?? null;
  const avgPct    = data.avg_percentile ?? null;
  const photo     = getPlayerPhotoUrl(playerName);
  const clubLogo  = getClubLogoUrl(playerName);

  const shots  = us.shot_coords ?? [];
  const nGoals = shots.filter((s) => s.result === "Goal").length;
  const nShots = shots.length;

  const posGroup = ctx?.pos_group ?? "";
  const total    = ctx?.total     ?? null;
  const ranks    = ctx?.ranks     ?? {};

  // Position-specific league averages for the radar reference polygon
  const posAvgs = leagueAvgs?.[posGroup] ?? null;

  return (
    <main className="max-w-[1420px] mx-auto px-6 pt-6 pb-16">

      {/* 1 ── Player header */}
      <Section>
        <PlayerHeader
          transfermarkt={tm}
          photoDataUri={photo}
          clubLogoDataUri={clubLogo}
          avgPercentile={avgPct}
          tmProfileUrl={tm?.profile_url ?? ""}
          minutes={us.minutes ?? 0}
          fallbackName={us.player_name ?? playerName}
          players={players}
          onCompare={onCompare}
          currentLeague={league}
        />
      </Section>

      {/* 2 ── Season stats */}
      <Section>
        <SeasonStats understat={us} />
      </Section>

      {/* 3 ── Advanced / 90 */}
      <Section>
        <div className="section-label mb-4">Advanced Stats / 90 min</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {METRICS.map(({ key, label, tooltip }) => {
            const val  = pct?.[key]                    ?? 0;
            const p    = pct?.percentiles?.[key]       ?? null;
            const rank = ranks[key]                    ?? null;
            return (
              <ErrorBoundary key={key}>
                <StatCard label={label} value={val} pct={p} rank={rank} total={total} tooltip={tooltip} />
              </ErrorBoundary>
            );
          })}
        </div>
        {!pct && (
          <p className="text-muted text-xs mt-3">
            ⚠ Percentiles unavailable — run{" "}
            <code className="bg-surface px-1 rounded">python3 percentiles.py</code>
          </p>
        )}
      </Section>

      {/* 4 ── Visualisations */}
      <Section>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <div className="section-label mb-3">Shot Map</div>
            <div className="rounded-2xl overflow-hidden border border-[rgba(165,231,255,0.08)]
                            shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
                 style={{ background: "#0d1117" }}>
              <ErrorBoundary>
                <ShotMap
                  shotCoords={shots}
                  playerName={us.player_name ?? playerName}
                  nGoals={nGoals}
                  nShots={nShots}
                />
              </ErrorBoundary>
            </div>
          </div>
          <div>
            <div className="section-label mb-3">Performance Radar</div>
            <div className="rounded-2xl overflow-hidden border border-[rgba(165,231,255,0.08)]
                            shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
                 style={{ background: "#0d1117" }}>
              <ErrorBoundary>
                <RadarChart
                  percentileRecord={pct}
                  playerName={us.player_name ?? playerName}
                  posGroup={POS_SINGULAR[posGroup] ?? posGroup}
                  minutes={us.minutes ?? 0}
                  avgPercentile={avgPct}
                  leagueAverages={posAvgs}
                />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      </Section>

      {/* 5 ── Scout analysis */}
      <section className="mb-8">
        <div className="section-label mb-4">Scout Analysis</div>
        <ErrorBoundary>
          <ScoutAnalysis
            percentileRecord={pct}
            goals={us.goals    ?? 0}
            assists={us.assists ?? 0}
            league={league}
          />
        </ErrorBoundary>
      </section>

      {/* 6 ── Similar Players */}
      <section className="mb-8">
        <div className="section-label mb-4">Similar Players</div>
        <ErrorBoundary>
          <SimilarPlayers
            data={similarData}
            loading={similarLoading}
            error={similarError}
            onNavigate={onNavigate}
          />
        </ErrorBoundary>
      </section>

      {/* Footer */}
      <hr className="border-[rgba(255,255,255,0.05)]" />
      <p className="text-center text-[11px] text-[#3c494e] mt-4 tracking-wide">
        Sources: Understat · Transfermarkt · 2025/26
        · Percentiles calculated among players with ≥ 180 min
      </p>
    </main>
  );
}
