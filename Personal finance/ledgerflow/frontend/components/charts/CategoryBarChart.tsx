"use client";

import { useState } from "react";
import { formatMoney } from "@/lib/format";
import type { TopCategory } from "@/lib/types";

const ROW_HEIGHT = 30;
const BAR_HEIGHT = 16;
const LABEL_WIDTH = 130;
const CHART_WIDTH = 640;
const RIGHT_PADDING = 90; // room for the value label past the bar tip

function barColor(row: TopCategory): string {
  if (row.budget_limit != null && row.budget_limit > 0) {
    const pct = row.total / row.budget_limit;
    if (pct > 1) return "var(--danger)";
    if (pct >= 0.8) return "var(--warning)";
  }
  return "var(--primary)";
}

export default function CategoryBarChart({
  data,
  currency,
  onSelect,
}: {
  data: TopCategory[];
  currency: string;
  onSelect?: (categoryName: string) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);

  if (data.length === 0) {
    return <div className="empty">No categorised spending yet this period.</div>;
  }

  const plotWidth = CHART_WIDTH - LABEL_WIDTH - RIGHT_PADDING;
  const maxValue = Math.max(...data.map((d) => Math.max(d.total, d.budget_limit ?? 0)), 1);
  const height = data.length * ROW_HEIGHT + 8;

  return (
    <div>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${height}`}
        style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}
        role="img"
        aria-label="Spending by category"
      >
        {data.map((row, i) => {
          const rowY = i * ROW_HEIGHT + 4;
          const barY = rowY + (ROW_HEIGHT - BAR_HEIGHT) / 2;
          const barLength = (row.total / maxValue) * plotWidth;
          const isHovered = hovered === row.name;

          return (
            <g
              key={row.name}
              style={{ cursor: onSelect ? "pointer" : "default" }}
              onMouseEnter={() => setHovered(row.name)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(row.name)}
              onBlur={() => setHovered(null)}
              onClick={() => onSelect?.(row.name)}
              tabIndex={onSelect ? 0 : -1}
              role={onSelect ? "button" : undefined}
              aria-label={`${row.name}: ${formatMoney(row.total, currency)}${row.budget_limit ? `, budget ${formatMoney(row.budget_limit, currency)}` : ""}`}
            >
              {/* Wider transparent hit target covering the whole row. */}
              <rect x={0} y={rowY} width={CHART_WIDTH} height={ROW_HEIGHT} fill="transparent" />

              <text
                x={LABEL_WIDTH - 10}
                y={rowY + ROW_HEIGHT / 2}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={11}
                fill={isHovered ? "var(--text)" : "var(--text-muted)"}
                pointerEvents="none"
              >
                {row.name}
              </text>

              {/* Track — a lighter step so the filled portion always reads against it. */}
              <rect
                x={LABEL_WIDTH}
                y={barY}
                width={plotWidth}
                height={BAR_HEIGHT}
                rx={4}
                fill="var(--bg)"
                pointerEvents="none"
              />
              <rect
                x={LABEL_WIDTH}
                y={barY}
                width={Math.max(2, barLength)}
                height={BAR_HEIGHT}
                rx={4}
                fill={barColor(row)}
                opacity={isHovered ? 1 : 0.9}
                pointerEvents="none"
              />

              {/* Budget-limit marker, when one exists. */}
              {row.budget_limit != null && row.budget_limit > 0 && (
                <line
                  x1={LABEL_WIDTH + (row.budget_limit / maxValue) * plotWidth}
                  x2={LABEL_WIDTH + (row.budget_limit / maxValue) * plotWidth}
                  y1={barY - 3}
                  y2={barY + BAR_HEIGHT + 3}
                  stroke="var(--text-muted)"
                  strokeWidth={2}
                  pointerEvents="none"
                />
              )}

              <text
                x={LABEL_WIDTH + plotWidth + 8}
                y={rowY + ROW_HEIGHT / 2}
                dominantBaseline="middle"
                fontSize={11}
                fill="var(--text)"
                pointerEvents="none"
              >
                {formatMoney(row.total, currency)}
              </text>
            </g>
          );
        })}
      </svg>

      <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.4rem" }}>
        The tick marks the budget limit — a bar reaching or passing it is over budget, independent of color. Color is a secondary
        cue (orange near the limit, red once it's breached).
      </p>

      <button
        type="button"
        className="btn btnSecondary btnSmall"
        style={{ marginTop: "0.4rem" }}
        onClick={() => setShowTable((v) => !v)}
      >
        {showTable ? "Hide table" : "Show as table"}
      </button>

      {showTable && (
        <div className="tableWrap spacer">
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Spent</th>
                <th>Budget</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.name}>
                  <td data-label="Category">{row.name}</td>
                  <td data-label="Spent">{formatMoney(row.total, currency)}</td>
                  <td data-label="Budget">{row.budget_limit != null ? formatMoney(row.budget_limit, currency) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
