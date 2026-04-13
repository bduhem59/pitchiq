const SIZE = 72;
const CX   = 36;
const CY   = 36;
const R    = 28;
const CIRC = 2 * Math.PI * R;

function gaugeColor(pct) {
  if (pct == null) return "#2b3546";
  if (pct >= 85)   return "#00d2ff";
  if (pct >= 67)   return "#47d6ff";
  if (pct >= 33)   return "#ffaa00";
  return "#ff4444";
}

function gaugeLevel(pct) {
  if (pct == null) return { label: "—",       color: "#3c4a5a" };
  if (pct >= 85)   return { label: "Elite",   color: "#00d2ff" };
  if (pct >= 67)   return { label: "Good",    color: "#47d6ff" };
  if (pct >= 33)   return { label: "Average", color: "#ffaa00" };
  return           { label: "Poor",    color: "#ff4444" };
}

function TopAccent({ color }) {
  return (
    <div className="absolute top-0 left-4 right-4 h-[2px] rounded-full opacity-70"
         style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }} />
  );
}

export default function StatCard({ label, value, pct, rank, total, tooltip }) {
  const color                        = gaugeColor(pct);
  const { label: lvl, color: lvlColor } = gaugeLevel(pct);
  const pctVal                       = pct ?? 0;
  const dashFill                     = (pctVal / 100) * CIRC;
  const dashGap                      = CIRC - dashFill;

  return (
    <div className="relative flex flex-col items-center pt-5 pb-4 px-3 rounded-2xl
                    border border-[rgba(165,231,255,0.07)]"
         style={{ background: "#121c2b" }}>

      <TopAccent color={color} />

      {/* Info tooltip */}
      {tooltip && (
        <div className="absolute top-2 right-2 group/tip">
          <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-full
                           border border-[rgba(165,231,255,0.4)] bg-[rgba(0,210,255,0.1)]
                           text-[10px] text-[rgba(165,231,255,0.7)] cursor-default select-none
                           hover:border-[#00d2ff] hover:shadow-[0_0_6px_rgba(0,210,255,0.3)]
                           transition-all duration-150">ℹ</span>
          <div className="absolute bottom-full right-0 mb-1.5 w-44 p-2.5 rounded-xl
                          bg-[#0a1623] border border-[rgba(165,231,255,0.12)]
                          text-[9px] text-muted leading-[1.5] whitespace-normal
                          opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150
                          pointer-events-none z-50 shadow-[0_8px_24px_rgba(0,0,0,0.6)]">
            {tooltip}
          </div>
        </div>
      )}

      {/* SVG ring */}
      <div className="relative mb-2">
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
          <circle cx={CX} cy={CY} r={R}
            fill="none" stroke="#1e2d3d" strokeWidth={5} />
          <circle cx={CX} cy={CY} r={R}
            fill="none" stroke={color} strokeWidth={5}
            strokeDasharray={`${dashFill} ${dashGap}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${CX} ${CY})`}
            style={{ transition: "stroke-dasharray 0.7s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[12px] font-black" style={{ color }}>
            {pct != null ? `${Math.round(pct)}%` : "—"}
          </span>
        </div>
      </div>

      {/* Value */}
      <div className="font-manrope font-black text-text leading-none tracking-tight mb-1"
           style={{ fontSize: "1.5rem", letterSpacing: "-0.5px" }}>
        {typeof value === "number" ? value.toFixed(2) : value}
      </div>

      {/* Metric label */}
      <div className="text-[13px] font-semibold uppercase tracking-widest mb-2 text-center"
           style={{ color: "#bbc9cf" }}>
        {label}
      </div>

      {/* Level pill */}
      <span className="text-[12px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full"
            style={{ color: lvlColor, background: `${lvlColor}1a` }}>
        {lvl}
      </span>

      {/* Rank */}
      {rank != null && total != null && (
        <div className="mt-1.5 text-[11px] text-muted">
          #{rank} / {total}
        </div>
      )}
    </div>
  );
}
