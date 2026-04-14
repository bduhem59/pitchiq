import _Plot from "react-plotly.js";
const Plot = _Plot.default ?? _Plot;

const PITCH_BG   = "#0d1117";
const LINE_COLOR = "rgba(165,231,255,0.2)";

const RESULT_COLORS = {
  Goal:        "#2ecc71",
  SavedShot:   "#e74c3c",
  BlockedShot: "#c0392b",
  MissedShots: "#7f8c8d",
  ShotOnPost:  "#f39c12",
};
const RESULT_LABELS = {
  Goal:        "Goal",
  SavedShot:   "Saved",
  BlockedShot: "Blocked",
  MissedShots: "Missed",
  ShotOnPost:  "Post",
};
const SITUATION_LABELS = {
  OpenPlay:       "Open Play",
  FromCorner:     "Corner",
  SetPiece:       "Set Piece",
  DirectFreekick: "Direct Free Kick",
  Penalty:        "Penalty",
};

// Uses scaled Statsbomb coordinates matching pitchShapes exactly
// xSb = x * 120 (depth), ySb = y * 80 (width)
function classifyZone(xSb, ySb) {
  if (xSb >= 114 && ySb >= 30 && ySb <= 50) return "Six Yard Box";
  if (xSb >= 102 && ySb >= 18 && ySb <= 62) return "Penalty Area";
  return "Outside Box";
}

function pitchShapes() {
  const rect = (x0, y0, x1, y1, fill, lc = LINE_COLOR) => ({
    type: "rect", x0, y0, x1, y1,
    fillcolor: fill, line: { color: lc, width: 1.5 },
  });
  const line = (x0, y0, x1, y1) => ({
    type: "line", x0, y0, x1, y1, line: { color: LINE_COLOR, width: 1.5 },
  });
  return [
    rect(0, 60, 80, 120, "rgba(0,0,0,0)"),
    line(0, 60, 80, 60),
    rect(18, 102, 62, 120, "rgba(71,214,255,0.06)", "rgba(71,214,255,0.25)"),
    rect(30, 114, 50, 120, "rgba(0,210,255,0.12)", "rgba(0,210,255,0.4)"),
    rect(36, 120, 44, 122, "rgba(255,255,255,0.04)"),
  ];
}

const ZONE_COLORS = {
  "Six Yard Box":  "#00d2ff",
  "Penalty Area":  "#47d6ff",
  "Outside Box":   "#3c4a5a",
};

export default function ShotMap({ shotCoords, playerName, nGoals, nShots, loading = false }) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 h-48 text-muted text-sm rounded-2xl border border-[rgba(255,255,255,0.05)]">
        <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        Loading shot map…
      </div>
    );
  }

  if (!shotCoords || shotCoords.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted text-sm rounded-2xl border border-[rgba(255,255,255,0.05)]">
        Shot map unavailable
      </div>
    );
  }

  // Group by result; classify zone using raw coords
  const groups = {};
  const zoneCounts = { "Six Yard Box": 0, "Penalty Area": 0, "Outside Box": 0 };

  for (const s of shotCoords) {
    const xSb  = s.x * 120;
    const ySb  = s.y * 80;
    const zone = classifyZone(xSb, ySb);
    zoneCounts[zone] = (zoneCounts[zone] ?? 0) + 1;
    const key = s.result || "MissedShots";
    if (!groups[key]) groups[key] = [];
    groups[key].push({ ...s, xSb, ySb, zone });
  }

  const total = shotCoords.length;

  const traces = Object.entries(groups).map(([result, shots]) => {
    const color = RESULT_COLORS[result] || "#7f8c8d";
    const label = RESULT_LABELS[result] || result;
    return {
      type:  "scatter",
      mode:  "markers",
      name:  label,
      x:     shots.map((s) => s.ySb),
      y:     shots.map((s) => s.xSb),
      marker: {
        color,
        size:     shots.map((s) => Math.max(s.xG, 0.005) * 38 + 6),
        opacity:  0.82,
        sizemode: "diameter",
        line: { width: 1.5, color: shots.map((s) => s.result === "Goal" ? "#ffffff" : "#1a1a2a") },
      },
      text: shots.map((s) => {
        const opp      = s.h_a === "h" ? s.a_team : s.h_team;
        const score    = s.h_goals != null && s.a_goals != null
          ? `${s.h_team} ${s.h_goals}–${s.a_goals} ${s.a_team}` : "";
        const matchLine = opp && score ? `c. ${opp} (${score})` : opp || "";
        const sit       = SITUATION_LABELS[s.situation] || s.situation || "";
        const header    = matchLine ? `<b>${s.minute}'  ${matchLine}</b>` : `<b>${s.minute}'</b>`;
        return `${header}<br>xG: ${Number(s.xG).toFixed(2)} — ${label}<br>${sit}`;
      }),
      hovertemplate: "%{text}<extra></extra>",
    };
  });

  // Penalty spot
  traces.push({
    type: "scatter", mode: "markers",
    x: [40], y: [108],
    marker: { color: LINE_COLOR, size: 4 },
    hoverinfo: "skip", showlegend: false,
  });

  // Centre arc
  const theta = Array.from({ length: 60 }, (_, i) => (i / 59) * Math.PI);
  traces.push({
    type: "scatter", mode: "lines",
    x: theta.map((t) => 40 + 10 * Math.cos(t)),
    y: theta.map((t) => 60 + 10 * Math.sin(t)),
    line: { color: LINE_COLOR, width: 1.5 },
    hoverinfo: "skip", showlegend: false,
  });

  const convPct = nShots > 0 ? ((nGoals / nShots) * 100).toFixed(1) : "0.0";

  const annotations = [
    { text: `<b>${convPct}% conversion</b>`, x: 80, y: 124,
      xref: "x", yref: "y", showarrow: false,
      font: { size: 10, color: "#003543", family: "Inter" },
      bgcolor: "#2ecc71", borderpad: 5, xanchor: "right", yanchor: "top" },
  ];

  const ZONE_ORDER = ["Six Yard Box", "Penalty Area", "Outside Box"];

  return (
    <div>
      <Plot
        data={traces}
        layout={{
          title: {
            text: `<b>${playerName}</b>  ·  Ligue 1  ·  ${nGoals} goals / ${nShots} shots`,
            x: 0.5, xanchor: "center",
            font: { color: "#d9e3f8", size: 12, family: "Manrope" },
          },
          shapes: pitchShapes(),
          annotations,
          paper_bgcolor: PITCH_BG,
          plot_bgcolor:  PITCH_BG,
          xaxis: { range: [-2, 82], showgrid: false, zeroline: false, visible: false },
          yaxis: { range: [58, 124], showgrid: false, zeroline: false, visible: false,
                   scaleanchor: "x", scaleratio: 1 },
          legend: {
            bgcolor: "rgba(13,17,23,0.85)",
            bordercolor: "rgba(165,231,255,0.15)", borderwidth: 1,
            font: { color: "#e6edf3", size: 10, family: "Inter" },
            orientation: "h", x: 0.5, xanchor: "center", y: -0.03, yanchor: "top",
          },
          margin: { t: 90, l: 15, r: 15, b: 15 },
          height: 480,
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
      />

      {/* Zone breakdown */}
      <div className="grid grid-cols-3 border-t border-[rgba(255,255,255,0.05)]"
           style={{ background: "#0d1117" }}>
        {ZONE_ORDER.map((zone, i) => {
          const count = zoneCounts[zone] ?? 0;
          const pct   = total > 0 ? Math.round((count / total) * 100) : 0;
          const color = ZONE_COLORS[zone];
          return (
            <div key={zone}
                 className={`flex flex-col items-center py-3 px-2
                             ${i < 2 ? "border-r border-[rgba(255,255,255,0.05)]" : ""}`}>
              <span className="font-manrope font-black text-lg leading-none"
                    style={{ color }}>{pct}%</span>
              <span className="text-[9px] text-muted uppercase tracking-wide mt-1 text-center">
                {zone}
              </span>
              <span className="text-[9px] text-muted/40 mt-0.5">{count} shots</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
