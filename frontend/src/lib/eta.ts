// Shared ETA/load formatting + derivation helpers - originally local to
// Dashboard.tsx, extracted so Nodes.tsx's own projected-load panel (see
// the parallel-processing work) uses the exact same math instead of a
// second, potentially-drifting copy.
import type { DeviceEtaMap, JobEstimate } from "@/lib/api"

export function formatDuration(seconds: number | undefined | null) {
  if (seconds == null) return "—"
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  if (m === 0) return `${s}s`
  const h = Math.floor(m / 60)
  if (h === 0) return `${m}m ${s}s`
  return `${h}h ${m % 60}m`
}

// The ring's fill isn't "percent complete" here - it's "how fast is this
// device relative to the others for this exact job": 100% = fastest
// available option, 0% = slowest, so switching devices gives an immediate
// visual sense of the tradeoff, not just a number to read.
export function relativeSpeedPercent(etas: DeviceEtaMap, deviceId: string) {
  const values = Object.values(etas).map((e) => e.eta_seconds)
  if (values.length === 0 || !(deviceId in etas)) return 0
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (max === min) return 100
  return ((max - etas[deviceId].eta_seconds) / (max - min)) * 100
}

// Compare only the selected processor's budget. An absent allocation in a
// supplied map means zero; an explicit null means unknown, not zero.
export function jobMemoryBudget(estimate: JobEstimate | undefined, deviceId: string) {
  if (!estimate) return undefined
  const budgets = estimate.peak_vram_by_device_mb
  if (budgets) return Object.hasOwn(budgets, deviceId) ? budgets[deviceId] : 0
  return estimate.peak_vram_mb // Compatibility with older backend responses.
}

// Uncalibrated additional budget plus observed use, against device capacity.
// Worker count changes CPU buffers, not model VRAM or measured throughput.
export function projectedLoadPercent(
  vramUsedMb: number | null,
  vramTotalMb: number | null,
  peakVramMb: number | null | undefined
) {
  if (vramUsedMb == null || !Number.isFinite(vramUsedMb) || vramUsedMb < 0 ||
      vramTotalMb == null || !Number.isFinite(vramTotalMb) || vramTotalMb <= 0 ||
      peakVramMb == null || !Number.isFinite(peakVramMb) || peakVramMb < 0) return null
  const projected = (vramUsedMb ?? 0) + (peakVramMb ?? 0)
  return Math.min(100, (projected / vramTotalMb) * 100)
}
