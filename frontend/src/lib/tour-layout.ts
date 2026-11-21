export interface RectLike { left: number; top: number; right: number; bottom: number; width: number; height: number }
export function computeTourCallout(target: RectLike | null, viewport: { width: number; height: number }, callout: { width: number; height: number }) {
  const margin = 16
  const maxWidth = Math.max(0, viewport.width - margin * 2)
  const maxHeight = Math.max(0, viewport.height - margin * 2)
  const width = Math.min(callout.width, 320, maxWidth)
  const height = Math.min(callout.height, maxHeight)
  const clamp = (value: number, maximum: number) => Math.max(Math.min(margin, maximum), Math.min(value, maximum))
  const x = target ? target.left : (viewport.width - width) / 2
  const below = target ? target.bottom + 20 : (viewport.height - height) / 2
  const y = target && below + height > viewport.height - margin ? target.top - 20 - height : below
  return { left: clamp(x, Math.max(0, viewport.width - margin - width)),
    top: clamp(y, Math.max(0, viewport.height - margin - height)), maxWidth, maxHeight }
}
