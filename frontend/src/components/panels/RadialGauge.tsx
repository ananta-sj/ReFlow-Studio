interface RadialGaugeProps {
  percent: number
  label: string
  sublabel: string
  color?: string
  size?: number
  /** Overrides the default "{percent}%" center text - e.g. a formatted
   * duration for an ETA gauge, where the ring's fill still means "percent"
   * (see Dashboard.tsx's relative-speed use) but the number to read isn't. */
  centerLabel?: string
}

export function RadialGauge({
  percent, label, sublabel, color = "var(--primary)", size = 108, centerLabel,
}: RadialGaugeProps) {
  const clamped = Math.max(0, Math.min(100, percent))
  const holeInset = size * 0.16

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="relative rounded-full transition-[background] duration-500"
        style={{
          width: size,
          height: size,
          background: `conic-gradient(${color} ${clamped}%, var(--muted) ${clamped}% 100%)`,
          boxShadow: `0 0 18px -4px ${color}`,
        }}
      >
        <div
          className="absolute rounded-full bg-card"
          style={{ inset: holeInset }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold text-foreground" style={{ fontFamily: "var(--font-mono)" }}>
            {centerLabel ?? `${Math.round(clamped)}%`}
          </span>
        </div>
      </div>
      <div className="text-center">
        <div className="text-xs font-medium text-muted-foreground">{label}</div>
        <div className="max-w-[120px] truncate text-[10px] text-muted-foreground/70">{sublabel}</div>
      </div>
    </div>
  )
}
