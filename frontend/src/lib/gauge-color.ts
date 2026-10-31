// Shared green->yellow->red color ramp for "load" gauges (CPU/RAM/VRAM
// utilization, Projected System Load) - deliberately NOT used for the
// Dashboard's "EST. TIME" gauge, whose ring fill means "how fast this
// device is relative to the others" (100% = fastest), not "how loaded is
// it" - painting that one red at high fill would look like a warning on
// the best available device, exactly backwards.
export function loadGaugeColor(percent: number): string {
  if (percent >= 85) return "var(--destructive)"
  if (percent >= 60) return "var(--warning)"
  return "var(--success)"
}
