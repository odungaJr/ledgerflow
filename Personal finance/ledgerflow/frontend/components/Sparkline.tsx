interface SparklinePoint {
  date: string;
  total_value: number;
}

export default function Sparkline({ data, height = 60 }: { data: SparklinePoint[]; height?: number }) {
  if (data.length === 0) {
    return <div className="empty">No value history yet.</div>;
  }
  if (data.length === 1) {
    return (
      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
        Add another value snapshot to see a trend.
      </p>
    );
  }

  const width = 600;
  const values = data.map((d) => d.total_value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((d.total_value - min) / range) * height;
    return `${x},${y}`;
  });

  const isUp = values[values.length - 1] >= values[0];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height: `${height}px`, display: "block" }}
    >
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={isUp ? "var(--success)" : "var(--danger)"}
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
