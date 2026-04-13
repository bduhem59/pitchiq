function Diff({ actual, expected }) {
  const d     = Math.round((actual - expected) * 10) / 10;
  const sign  = d >= 0 ? "+" : "";
  const color = d >= 0 ? "#4ade80" : "#f87171";
  return (
    <span style={{ fontSize: 11, fontWeight: 700, color, lineHeight: 1 }}>
      {sign}{d.toFixed(1)}
    </span>
  );
}

function Tooltip({ text }) {
  return (
    <div className="group/tip absolute top-2 right-2">
      <span className="inline-flex items-center justify-center w-[18px] h-[18px] rounded-full
                       border border-[rgba(165,231,255,0.4)] bg-[rgba(0,210,255,0.1)]
                       cursor-default select-none
                       hover:border-[#00d2ff] hover:shadow-[0_0_6px_rgba(0,210,255,0.3)]
                       transition-all duration-150"
            style={{ width: 18, height: 18 }}>
        <svg width="4" height="8" viewBox="0 0 4 8" fill="none">
          <circle cx="2" cy="1" r="1" fill="rgba(165,231,255,0.8)" />
          <rect x="1" y="3" width="2" height="5" rx="1" fill="rgba(165,231,255,0.8)" />
        </svg>
      </span>
      <div className="absolute bottom-full right-0 mb-1.5 w-44 p-2.5 rounded-xl
                      bg-[#0a1623] border border-[rgba(165,231,255,0.12)]
                      text-[9px] text-muted leading-[1.5] whitespace-normal
                      opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150
                      pointer-events-none z-50 shadow-[0_8px_24px_rgba(0,0,0,0.6)]">
        {text}
      </div>
    </div>
  );
}

function StatCard({ label, value, diff, tooltip }) {
  return (
    <div className="relative flex flex-col items-center justify-center h-28 px-3 rounded-2xl
                    border border-[rgba(255,255,255,0.05)]"
         style={{ background: "#162030" }}>
      {tooltip && <Tooltip text={tooltip} />}
      {/* Value + optional diff on same baseline line */}
      <div className="inline-flex items-baseline gap-1 mb-2" style={{ lineHeight: 1 }}>
        <span className="font-manrope font-black text-text"
              style={{ fontSize: "clamp(1.6rem,2.8vw,2.2rem)", letterSpacing: "-1px", lineHeight: 1 }}>
          {value}
        </span>
        {diff ?? null}
      </div>
      {/* Label — always present, always same position */}
      <div className="text-[10px] text-muted font-semibold uppercase tracking-[1.5px] text-center">
        {label}
      </div>
    </div>
  );
}

export default function SeasonStats({ understat }) {
  const us      = understat || {};
  const goals   = us.goals   ?? 0;
  const assists = us.assists  ?? 0;
  const xg      = us.xG      ?? 0;
  const xa      = us.xA      ?? 0;
  const games   = us.games   ?? 0;
  const minutes = us.minutes ?? 0;

  return (
    <section className="mb-8">
      <div className="section-label mb-4">Current Season</div>
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        <StatCard label="Matches" value={games} />
        <StatCard label="Minutes" value={minutes.toLocaleString("en-US")} />
        <StatCard label="Goals"   value={goals} />
        <StatCard label="Assists" value={assists} />
        <StatCard label="xG" value={xg.toFixed(1)}
          diff={<Diff actual={goals}   expected={xg} />}
          tooltip="Expected goals based on shot quality. The exposant shows goals scored vs xG." />
        <StatCard label="xA" value={xa.toFixed(1)}
          diff={<Diff actual={assists} expected={xa} />}
          tooltip="Expected assists based on pass quality leading to shots. The exposant shows actual assists vs xA." />
      </div>
    </section>
  );
}
