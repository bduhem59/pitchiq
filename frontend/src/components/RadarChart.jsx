import _Plot from "react-plotly.js";
const Plot = _Plot.default ?? _Plot;

const METRICS = ["xG_90", "npxG_90", "xA_90", "xGChain_90", "xGBuildup_90"];
const LABELS  = ["xG/90", "npxG/90", "xA/90", "xGChain/90", "xGBuildup/90"];

// Max normalisation values (95th percentile Ligue 1 reference)
const MAX_VALS = {
  xG_90: 0.9, npxG_90: 0.7, xA_90: 0.4, xGChain_90: 1.0, xGBuildup_90: 0.5,
};

export default function RadarChart({ percentileRecord, playerName, posGroup, minutes, avgPercentile, leagueAverages }) {

  if (!percentileRecord) {
    return (
      <div className="flex items-center justify-center h-48 text-muted text-sm rounded-2xl border border-[rgba(255,255,255,0.05)]">
        Radar unavailable
      </div>
    );
  }

  const vals = METRICS.map((k) => {
    const raw = percentileRecord[k] ?? 0;
    const max = MAX_VALS[k] ?? 1;
    return Math.min(raw / max, 1);
  });
  // Close polygon
  const valsClose   = [...vals, vals[0]];
  const labelsClose = [...LABELS, LABELS[0]];

  // Position-specific league average reference polygon
  const avgVals = METRICS.map((k) => {
    const raw = leagueAverages?.[k] ?? null;
    if (raw == null) return 0.5; // fallback to median if no data
    const max = MAX_VALS[k] ?? 1;
    return Math.min(raw / max, 1);
  });
  const avgValsClose = [...avgVals, avgVals[0]];

  const topPct = avgPercentile != null ? Math.round(100 - avgPercentile) : null;

  const annotations = topPct != null
    ? [{ text: `<b>Top ${topPct}%</b>`, xref: "paper", yref: "paper",
         x: 1.0, y: 1.06, showarrow: false,
         font: { size: 10, color: "#003543", family: "Inter" },
         bgcolor: "#00d2ff", borderpad: 5, xanchor: "right", yanchor: "top" }]
    : [];

  return (
    <Plot
      data={[
        {
          type: "scatterpolar",
          r: valsClose,
          theta: labelsClose,
          fill: "toself",
          fillcolor: "rgba(0,210,255,0.12)",
          line: { color: "#00d2ff", width: 2 },
          name: playerName,
          hovertemplate: "%{theta}: %{r:.2f}<extra></extra>",
        },
        // Position-specific league average reference
        {
          type: "scatterpolar",
          r: avgValsClose,
          theta: labelsClose,
          fill: "toself",
          fillcolor: "rgba(255,255,255,0.03)",
          line: { color: "rgba(255,255,255,0.25)", width: 1.5, dash: "dot" },
          name: `${posGroup} avg.`,
          hoverinfo: "skip",
        },
      ]}
      layout={{
        title: {
          text: `<b>${playerName}</b>  ·  ${posGroup}  ·  ${minutes} min`,
          x: 0.5, xanchor: "center",
          font: { color: "#d9e3f8", size: 12, family: "Manrope" },
        },
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
          font: { color: "#bbc9cf", size: 10, family: "Inter" },
          bgcolor: "rgba(13,17,23,0.8)", bordercolor: "rgba(165,231,255,0.1)", borderwidth: 1,
          x: 0.5, xanchor: "center", y: -0.1, yanchor: "top",
        },
        annotations,
        margin: { t: 90, l: 40, r: 40, b: 20 },
        height: 480,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
    />
  );
}
