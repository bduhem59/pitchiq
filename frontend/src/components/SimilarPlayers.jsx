import { getPlayerPhotoUrl } from "../api";

const LEAGUE_LABELS = {
  Ligue_1:    "Ligue 1",
  EPL:        "Premier League",
  La_Liga:    "La Liga",
  Bundesliga: "Bundesliga",
  Serie_A:    "Serie A",
};

const POS_LABELS = {
  attaquants:  "Forward",
  milieux:     "Midfielder",
  défenseurs:  "Defender",
};

function SimilarCard({ player, onNavigate }) {
  const { player_name, team, league, position_group, similarity, avg_percentile, closest_metrics } = player;
  const photoSrc = getPlayerPhotoUrl(player_name);

  const simColor =
    similarity >= 85 ? "#00d2ff" :
    similarity >= 70 ? "#4ade80" :
    "#bbc9cf";

  return (
    <button
      onClick={() => onNavigate?.("player", player_name, league)}
      className="relative flex flex-col items-center text-center p-5 rounded-2xl
                 border border-[rgba(255,255,255,0.06)] transition-all duration-200
                 hover:border-[rgba(0,210,255,0.3)] hover:shadow-[0_0_24px_rgba(0,210,255,0.08)]
                 cursor-pointer w-full"
      style={{ background: "#0f1923" }}>

      {/* Similarity badge — top-right of card */}
      <div className="absolute top-3 right-3 text-[10px] font-black rounded-full
                      px-1.5 py-0.5 leading-none"
           style={{ background: `${simColor}22`, color: simColor, border: `1px solid ${simColor}55` }}>
        {similarity}%
      </div>

      {/* Photo */}
      <div className="mb-3">
        <img
          src={photoSrc}
          alt={player_name}
          onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.nextSibling.style.display = "flex"; }}
          className="w-20 h-28 object-cover object-top rounded-xl"
          style={{ border: "1px solid rgba(165,231,255,0.12)" }}
        />
        <div className="w-20 h-28 rounded-xl bg-surface border border-[rgba(255,255,255,0.05)]
                        items-center justify-center text-4xl text-[#3c494e] hidden">
          👤
        </div>
      </div>

      {/* Name */}
      <div className="font-manrope font-black text-text leading-tight mb-1"
           style={{ fontSize: "clamp(0.8rem,1.5vw,1rem)", letterSpacing: "-0.4px" }}>
        {player_name}
      </div>

      {/* Team */}
      <div className="text-[10px] text-muted mb-1">{team}</div>

      {/* League + position on the same line */}
      <div className="flex items-center gap-1.5 justify-center mb-3 flex-wrap">
        {league && (
          <span className="text-[9px] font-semibold uppercase tracking-[1px]"
                style={{ color: "rgba(0,210,255,0.5)" }}>
            {LEAGUE_LABELS[league] || league}
          </span>
        )}
        {league && position_group && (
          <span className="text-[9px] text-muted/30">·</span>
        )}
        {position_group && (
          <span className="text-[9px] font-semibold uppercase tracking-[1px] text-muted/60">
            {POS_LABELS[position_group] || position_group}
          </span>
        )}
      </div>

      {/* Avg percentile */}
      {avg_percentile != null && (
        <div className="text-[10px] font-bold mb-3"
             style={{ color: avg_percentile >= 75 ? "#00d2ff" : "#bbc9cf" }}>
          {Math.round(avg_percentile)}th pct
        </div>
      )}

      {/* Closest metrics */}
      {closest_metrics?.length > 0 && (
        <div className="flex flex-col gap-1 w-full">
          {closest_metrics.map((m) => (
            <div key={m.key}
                 className="flex items-center justify-between px-2.5 py-1 rounded-lg"
                 style={{ background: "rgba(0,210,255,0.05)", border: "1px solid rgba(0,210,255,0.08)" }}>
              <span className="text-[9px] text-muted/70 uppercase tracking-wide">{m.label}</span>
              <span className="text-[10px] font-bold text-accent">{m.value}</span>
            </div>
          ))}
        </div>
      )}
    </button>
  );
}

export default function SimilarPlayers({ data, loading, error, onNavigate }) {
  if (loading) return (
    <div className="flex items-center gap-3 text-muted text-sm py-4">
      <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin shrink-0" />
      Finding similar players…
    </div>
  );

  if (error || !data || data.length === 0) return null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {data.map((p) => (
        <SimilarCard key={`${p.player_name}-${p.league}`} player={p} onNavigate={onNavigate} />
      ))}
    </div>
  );
}
