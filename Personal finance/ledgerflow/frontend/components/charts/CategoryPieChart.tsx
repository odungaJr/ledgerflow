"use client";

import { useState } from "react";
import { formatMoney } from "@/lib/format";
import type { TopCategory } from "@/lib/types";

const SIZE = 220;
const CENTER = SIZE / 2;
const RADIUS = SIZE / 2 - 4;
const INNER_RADIUS = RADIUS * 0.6; // donut hole, for a center total label
const CHART_COLORS = [
  "var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)",
  "var(--chart-5)", "var(--chart-6)", "var(--chart-7)", "var(--chart-8)",
];

function polarToCartesian(angle: number, radius: number): { x: number; y: number } {
  const rad = (angle - 90) * (Math.PI / 180);
  return { x: CENTER + radius * Math.cos(rad), y: CENTER + radius * Math.sin(rad) };
}

function donutSlicePath(startAngle: number, endAngle: number): string {
  const outerStart = polarToCartesian(startAngle, RADIUS);
  const outerEnd = polarToCartesian(endAngle, RADIUS);
  const innerStart = polarToCartesian(endAngle, INNER_RADIUS);
  const innerEnd = polarToCartesian(startAngle, INNER_RADIUS);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;

  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${RADIUS} ${RADIUS} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerStart.x} ${innerStart.y}`,
    `A ${INNER_RADIUS} ${INNER_RADIUS} 0 ${largeArc} 0 ${innerEnd.x} ${innerEnd.y}`,
    "Z",
  ].join(" ");
}

export default function CategoryPieChart({
  data,
  currency,
  onSelect,
}: {
  data: TopCategory[];
  currency: string;
  onSelect?: (categoryName: string) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);

  if (data.length === 0) {
    return <div className="empty">No categorised spending yet this period.</div>;
  }

  const total = data.reduce((sum, d) => sum + d.total, 0);

  let angle = 0;
  const slices = data.map((row, i) => {
    const fraction = total > 0 ? row.total / total : 0;
    const startAngle = angle;
    // Cap just short of a full circle — the arc path math degenerates to a
    // zero-length arc when start and end angle coincide (e.g. a single
    // category holding 100% of spend).
    const endAngle = Math.min(angle + fraction * 360, 359.999);
    angle = endAngle;
    return { row, color: CHART_COLORS[i % CHART_COLORS.length], startAngle, endAngle, fraction };
  });

  const activeSlice = slices.find((s) => s.row.name === hovered);

  return (
    <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", alignItems: "center" }}>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        style={{ width: "100%", maxWidth: SIZE, height: "auto", flexShrink: 0 }}
        role="img"
        aria-label="Spending share by category"
      >
        {slices.map((s) => (
          <path
            key={s.row.name}
            d={donutSlicePath(s.startAngle, s.endAngle)}
            fill={s.color}
            opacity={hovered === null || hovered === s.row.name ? 1 : 0.35}
            stroke="var(--surface)"
            strokeWidth={2}
            style={{ cursor: onSelect ? "pointer" : "default", transition: "opacity 0.15s ease" }}
            onMouseEnter={() => setHovered(s.row.name)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(s.row.name)}
            onBlur={() => setHovered(null)}
            onClick={() => onSelect?.(s.row.name)}
            tabIndex={onSelect ? 0 : -1}
            role={onSelect ? "button" : undefined}
            aria-label={`${s.row.name}: ${formatMoney(s.row.total, currency)}, ${(s.fraction * 100).toFixed(1)}% of spending`}
          />
        ))}

        <text x={CENTER} y={CENTER - 6} textAnchor="middle" fontSize={11} fill="var(--text-muted)">
          {activeSlice ? activeSlice.row.name : "Total"}
        </text>
        <text x={CENTER} y={CENTER + 14} textAnchor="middle" fontSize={13} fontWeight={700} fill="var(--text)">
          {formatMoney(activeSlice ? activeSlice.row.total : total, currency)}
        </text>
      </svg>

      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem", flex: 1, minWidth: 180 }}>
        {slices.map((s) => (
          <li
            key={s.row.name}
            onMouseEnter={() => setHovered(s.row.name)}
            onMouseLeave={() => setHovered(null)}
            onClick={() => onSelect?.(s.row.name)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              fontSize: "0.85rem",
              cursor: onSelect ? "pointer" : "default",
              opacity: hovered === null || hovered === s.row.name ? 1 : 0.5,
            }}
          >
            <span style={{ width: 10, height: 10, borderRadius: 2, background: s.color, flexShrink: 0 }} />
            <span style={{ flex: 1, color: "var(--text)" }}>{s.row.name}</span>
            <span style={{ color: "var(--text-muted)" }}>{(s.fraction * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
