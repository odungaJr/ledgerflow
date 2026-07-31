"use client";

import { useState } from "react";
import { formatMoney } from "@/lib/format";
import type { MonthlyTrendPoint } from "@/lib/types";

const WIDTH = 640;
const HEIGHT = 280;
const MARGIN = { top: 28, right: 12, bottom: 28, left: 56 };
const PLOT_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = HEIGHT - MARGIN.top - MARGIN.bottom;
const BAR_MAX_WIDTH = 24;
const BAR_GAP = 3;

function niceCeil(value: number): number {
  if (value <= 0) return 1;
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

export default function IncomeExpenseChart({
  data,
  currency,
}: {
  data: MonthlyTrendPoint[];
  currency: string;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  if (data.length === 0) {
    return <div className="empty">No transaction history yet.</div>;
  }

  const maxRaw = Math.max(1, ...data.map((d) => Math.max(d.total_income, d.total_expenses)));
  const maxValue = niceCeil(maxRaw);
  const tickCount = 4;
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => (maxValue / tickCount) * i);

  const groupWidth = PLOT_WIDTH / data.length;
  const barWidth = Math.min(BAR_MAX_WIDTH, (groupWidth - BAR_GAP * 3) / 2);

  function y(value: number): number {
    return MARGIN.top + PLOT_HEIGHT - (value / maxValue) * PLOT_HEIGHT;
  }

  return (
    <div>
      {/* Legend — mandatory identity channel for 2 series, never color-matching alone. */}
      <div style={{ display: "flex", gap: "1.25rem", marginBottom: "0.25rem", fontSize: "0.8rem" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--success)", display: "inline-block" }} />
          <span style={{ color: "var(--text-muted)" }}>Income</span>
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--danger)", display: "inline-block" }} />
          <span style={{ color: "var(--text-muted)" }}>Expenses</span>
        </span>
      </div>

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}
        role="img"
        aria-label="Income versus expenses by month"
      >
        {/* Gridlines — hairline, recessive, one step off the surface. */}
        {ticks.map((t, i) => (
          <line
            key={i}
            x1={MARGIN.left}
            x2={WIDTH - MARGIN.right}
            y1={y(t)}
            y2={y(t)}
            stroke="var(--border)"
            strokeWidth={1}
          />
        ))}
        {ticks.map((t, i) => (
          <text key={i} x={MARGIN.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize={10} fill="var(--text-muted)">
            {t >= 1_000_000 ? `${(t / 1_000_000).toFixed(1)}M` : t >= 1_000 ? `${Math.round(t / 1000)}K` : Math.round(t)}
          </text>
        ))}

        {data.map((d, i) => {
          const groupX = MARGIN.left + i * groupWidth;
          const incomeX = groupX + groupWidth / 2 - barWidth - BAR_GAP / 2;
          const expenseX = groupX + groupWidth / 2 + BAR_GAP / 2;
          const incomeY = y(d.total_income);
          const expenseY = y(d.total_expenses);
          const baseline = y(0);
          const isHovered = hoverIndex === i;

          return (
            <g key={d.period}>
              {/* Wider transparent hit target than the bars themselves. */}
              <rect
                x={groupX}
                y={MARGIN.top}
                width={groupWidth}
                height={PLOT_HEIGHT}
                fill="transparent"
                onMouseEnter={() => setHoverIndex(i)}
                onMouseLeave={() => setHoverIndex(null)}
                onFocus={() => setHoverIndex(i)}
                onBlur={() => setHoverIndex(null)}
                tabIndex={0}
                aria-label={`${d.period}: income ${formatMoney(d.total_income, currency)}, expenses ${formatMoney(d.total_expenses, currency)}`}
              />

              <rect
                x={incomeX}
                y={incomeY}
                width={barWidth}
                height={Math.max(0, baseline - incomeY)}
                rx={4}
                fill="var(--success)"
                opacity={isHovered ? 1 : 0.85}
                pointerEvents="none"
              />
              <rect
                x={expenseX}
                y={expenseY}
                width={barWidth}
                height={Math.max(0, baseline - expenseY)}
                rx={4}
                fill="var(--danger)"
                opacity={isHovered ? 1 : 0.85}
                pointerEvents="none"
              />

              {/* Direct labels at the bar tip — shown on hover only, per "label selectively". */}
              {isHovered && (
                <>
                  <text x={incomeX + barWidth / 2} y={incomeY - 6} textAnchor="middle" fontSize={10} fill="var(--text)" pointerEvents="none">
                    {formatMoney(d.total_income, currency)}
                  </text>
                  <text x={expenseX + barWidth / 2} y={expenseY - 6} textAnchor="middle" fontSize={10} fill="var(--text)" pointerEvents="none">
                    {formatMoney(d.total_expenses, currency)}
                  </text>
                </>
              )}

              <text
                x={groupX + groupWidth / 2}
                y={HEIGHT - MARGIN.bottom + 16}
                textAnchor="middle"
                fontSize={10}
                fill="var(--text-muted)"
                pointerEvents="none"
              >
                {d.period.split(" ")[0]}
              </text>
            </g>
          );
        })}
      </svg>

      <button
        type="button"
        className="btn btnSecondary btnSmall"
        style={{ marginTop: "0.5rem" }}
        onClick={() => setShowTable((v) => !v)}
      >
        {showTable ? "Hide table" : "Show as table"}
      </button>

      {showTable && (
        <div className="tableWrap spacer">
          <table>
            <thead>
              <tr>
                <th>Month</th>
                <th>Income</th>
                <th>Expenses</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.period}>
                  <td data-label="Month">{d.period}</td>
                  <td data-label="Income">{formatMoney(d.total_income, currency)}</td>
                  <td data-label="Expenses">{formatMoney(d.total_expenses, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
