const METRIC_NAMES = {
  xG_90:        "xG / 90",
  npxG_90:      "npxG / 90",
  xA_90:        "xA / 90",
  xGChain_90:   "xGChain / 90",
  xGBuildup_90: "xGBuildup / 90",
};

function dotColor(pct) {
  if (pct >= 85) return "#00d2ff";
  if (pct >= 67) return "#47d6ff";
  if (pct >= 33) return "#ffaa00";
  return "#ff4444";
}

function Bullet({ metricKey, pct, badgeBg }) {
  const dot = dotColor(pct);
  return (
    <div className="flex items-center justify-between py-2
                    border-b border-[rgba(255,255,255,0.04)] last:border-0">
      <div className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dot }} />
        <span className="text-xs text-text">{METRIC_NAMES[metricKey] || metricKey}</span>
      </div>
      <span className="text-[10px] font-black px-2 py-0.5 rounded-full text-white"
            style={{ background: badgeBg }}>
        {Math.round(pct)}th
      </span>
    </div>
  );
}

function VerdictGauge({ score, color }) {
  const SIZE = 88; const CX = 44; const CY = 44; const R = 34;
  const CIRC = 2 * Math.PI * R;
  const fill = ((score / 10) * 100 / 100) * CIRC;
  const gap  = CIRC - fill;
  return (
    <div className="relative shrink-0">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="#1e2d3d" strokeWidth={6} />
        <circle cx={CX} cy={CY} r={R} fill="none"
          stroke={color} strokeWidth={6}
          strokeDasharray={`${fill} ${gap}`} strokeLinecap="round"
          transform={`rotate(-90 ${CX} ${CY})`} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-manrope font-black text-text leading-none"
              style={{ fontSize: "1.35rem", letterSpacing: "-0.5px" }}>{score}</span>
        <span className="text-[9px] text-muted">/10</span>
      </div>
    </div>
  );
}

export default function ScoutAnalysis({ percentileRecord, goals, assists }) {
  const pcts   = percentileRecord?.percentiles ?? {};
  const vals   = percentileRecord ?? {};
  const pctArr = Object.values(pcts).filter((v) => v != null);
  const avgPct = pctArr.length ? pctArr.reduce((a, b) => a + b, 0) / pctArr.length : null;

  const strong = Object.entries(pcts).filter(([, v]) => v > 67).sort((a, b) => b[1] - a[1]);
  const weak   = Object.entries(pcts).filter(([, v]) => v < 33).sort((a, b) => a[1] - b[1]);

  let verdictLabel = "Watch List";
  let verdictColor = "#ff4444";
  let verdictNote  = avgPct != null ? Number((avgPct / 10).toFixed(1)) : null;
  let verdictText  = "Current performance remains below the positional median. Worth monitoring over time.";

  if (avgPct != null && avgPct >= 75) {
    verdictLabel = "Recommended";
    verdictColor = "#2ecc71";
    verdictText  = "High-level offensive profile. Metrics place this player among the best at his position in Ligue 1.";
  } else if (avgPct != null && avgPct >= 50) {
    verdictLabel = "Promising";
    verdictColor = "#ffaa00";
    verdictText  = "Solid profile with notable strengths. Improvement in creative metrics could take him to the next level.";
  }

  const xg90 = vals.xG_90 ?? 0;

  const cardBase = "rounded-2xl border border-[rgba(255,255,255,0.05)] p-5";

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

      {/* Strengths */}
      <div className={cardBase} style={{ background: "#1a2233" }}>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm">⚡</span>
          <span className="font-manrope text-[10px] font-black uppercase tracking-[2px] text-text">
            Tactical Strengths
          </span>
        </div>
        {strong.length > 0
          ? strong.map(([k, v]) => <Bullet key={k} metricKey={k} pct={v} badgeBg="#0d5c30" />)
          : <p className="text-muted text-xs italic">No strengths identified</p>
        }
      </div>

      {/* Development */}
      <div className={cardBase} style={{ background: "#1a2233" }}>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm">📈</span>
          <span className="font-manrope text-[10px] font-black uppercase tracking-[2px] text-text">
            Development Areas
          </span>
        </div>
        {weak.length > 0
          ? weak.map(([k, v]) => <Bullet key={k} metricKey={k} pct={v} badgeBg="#5c3a00" />)
          : <p className="text-muted text-xs italic">No areas identified</p>
        }
      </div>

      {/* Verdict */}
      <div className={`${cardBase} flex flex-col`}
           style={{
             background: "linear-gradient(135deg, rgba(20,34,55,0.9), rgba(13,22,35,0.95))",
             border: "1px solid rgba(165,231,255,0.12)",
           }}>
        <div className="font-manrope text-[10px] font-black uppercase tracking-[2px] text-primary mb-4">
          Scout Verdict
        </div>
        <div className="flex items-center gap-4 mb-3">
          {verdictNote != null && <VerdictGauge score={verdictNote} color={verdictColor} />}
          <div>
            <span className="inline-block px-2.5 py-1 rounded-full text-[10px] font-black text-white mb-2"
                  style={{ background: verdictColor }}>
              {verdictLabel}
            </span>
            <p className="text-muted text-[11px] leading-relaxed">{verdictText}</p>
          </div>
        </div>
        <div className="mt-auto grid grid-cols-3 rounded-xl overflow-hidden
                        border border-[rgba(255,255,255,0.06)]">
          {[
            { label: "Goals",   value: goals },
            { label: "Assists", value: assists },
            { label: "xG/90",   value: xg90.toFixed(2) },
          ].map(({ label, value }, i) => (
            <div key={label}
                 className={`text-center py-2.5 px-2
                             ${i < 2 ? "border-r border-[rgba(255,255,255,0.06)]" : ""}`}>
              <div className="font-manrope font-black text-text text-lg leading-none">{value}</div>
              <div className="text-[9px] text-muted uppercase tracking-wide mt-1">{label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
