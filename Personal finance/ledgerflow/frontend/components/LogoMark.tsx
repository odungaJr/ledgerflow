export default function LogoMark({ size = 56 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="LedgerFlow"
    >
      <rect width="64" height="64" rx="18" fill="var(--primary)" />
      <rect x="15" y="34" width="9" height="16" rx="2.5" fill="white" opacity="0.75" />
      <rect x="27.5" y="25" width="9" height="25" rx="2.5" fill="white" opacity="0.9" />
      <rect x="40" y="14" width="9" height="36" rx="2.5" fill="white" />
    </svg>
  );
}
