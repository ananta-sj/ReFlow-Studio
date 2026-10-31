// Detailed HSV color picker: a draggable hue ring plus a saturation/value
// square, with a hex field for exact entry - the "any color to any color"
// picker requested for the app's accent color. Deliberately built from
// scratch (no color-picker dependency) since the interaction (ring +
// square, both pointer-draggable with capture) is simple enough not to
// warrant one, and it keeps this fully themeable/self-contained.
import { useRef, useState } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { hexToHsv, hsvToHex, type HSV } from "@/lib/use-accent-color"
import { cn } from "@/lib/utils"

const RING_SIZE = 180
const RING_THICKNESS = 22
const SQUARE_SIZE = RING_SIZE - RING_THICKNESS * 2 - 16

interface ColorPickerProps {
  value: string
  onChange: (hex: string) => void
  onReset?: () => void
}

export function ColorPicker({ value, onChange, onReset }: ColorPickerProps) {
  const hsv = hexToHsv(value) ?? { h: 90, s: 70, v: 100 }
  const [draft, setDraft] = useState({ value, text: value })
  const hexInput = draft.value === value ? draft.text : value
  if (draft.value !== value) setDraft({ value, text: value })
  const ringRef = useRef<HTMLDivElement>(null)
  const squareRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef<"ring" | "square" | null>(null)

  function commit(next: HSV) {
    const hex = hsvToHex(next)
    setDraft({ value: hex, text: hex })
    onChange(hex)
  }

  function handleRingPointer(e: React.PointerEvent) {
    const el = ringRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const angle = Math.atan2(e.clientY - cy, e.clientX - cx)
    let h = (angle * 180) / Math.PI + 90
    if (h < 0) h += 360
    commit({ ...hsv, h })
  }

  function handleSquarePointer(e: React.PointerEvent) {
    const el = squareRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))
    commit({ ...hsv, s: x * 100, v: (1 - y) * 100 })
  }

  function startDrag(target: "ring" | "square", handler: (e: React.PointerEvent) => void) {
    return (e: React.PointerEvent) => {
      e.stopPropagation()
      draggingRef.current = target
      ;(e.target as Element).setPointerCapture(e.pointerId)
      handler(e)
    }
  }

  function onDragMove(e: React.PointerEvent) {
    if (draggingRef.current === "ring") handleRingPointer(e)
    else if (draggingRef.current === "square") handleSquarePointer(e)
  }

  function endDrag() {
    draggingRef.current = null
  }

  function handleHexSubmit(raw: string) {
    const parsed = hexToHsv(raw)
    const next = parsed ? hsvToHex(parsed) : value
    setDraft({ value: next, text: raw })
    if (parsed) onChange(next)
  }

  const knobAngleRad = ((hsv.h - 90) * Math.PI) / 180
  const knobRadius = RING_SIZE / 2 - RING_THICKNESS / 2
  const knobX = RING_SIZE / 2 + knobRadius * Math.cos(knobAngleRad)
  const knobY = RING_SIZE / 2 + knobRadius * Math.sin(knobAngleRad)

  return (
    <div className="flex flex-col items-center gap-4">
      <div
        ref={ringRef}
        onPointerDown={startDrag("ring", handleRingPointer)}
        onPointerMove={onDragMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        className="relative shrink-0 cursor-pointer touch-none rounded-full"
        style={{
          width: RING_SIZE,
          height: RING_SIZE,
          background: "conic-gradient(from 0deg, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000)",
          WebkitMaskImage: `radial-gradient(circle, transparent ${RING_SIZE / 2 - RING_THICKNESS}px, black ${RING_SIZE / 2 - RING_THICKNESS + 1}px)`,
          maskImage: `radial-gradient(circle, transparent ${RING_SIZE / 2 - RING_THICKNESS}px, black ${RING_SIZE / 2 - RING_THICKNESS + 1}px)`,
        }}
      >
        <div
          className="pointer-events-none absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-[0_0_0_1px_rgba(0,0,0,0.4)]"
          style={{ left: knobX, top: knobY, background: `hsl(${hsv.h}, 100%, 50%)` }}
        />

        {/* Saturation/Value square, centered inside the ring's hole */}
        <div
          ref={squareRef}
          onPointerDown={startDrag("square", handleSquarePointer)}
          onPointerMove={onDragMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          className="absolute cursor-pointer touch-none rounded-sm"
          style={{
            width: SQUARE_SIZE,
            height: SQUARE_SIZE,
            left: (RING_SIZE - SQUARE_SIZE) / 2,
            top: (RING_SIZE - SQUARE_SIZE) / 2,
            backgroundColor: `hsl(${hsv.h}, 100%, 50%)`,
            backgroundImage:
              "linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, transparent)",
          }}
        >
          <div
            className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-[0_0_0_1px_rgba(0,0,0,0.4)]"
            style={{ left: `${hsv.s}%`, top: `${100 - hsv.v}%` }}
          />
        </div>
      </div>

      <div className="flex w-full max-w-[220px] items-center gap-2">
        <div
          className="h-8 w-8 shrink-0 rounded-md border border-border"
          style={{ backgroundColor: value }}
        />
        <Input
          value={hexInput}
          onChange={(e) => handleHexSubmit(e.target.value)}
          className={cn("font-mono text-xs", !hexToHsv(hexInput) && "border-destructive")}
          maxLength={7}
        />
      </div>

      {onReset && (
        <Button variant="outline" size="sm" onClick={onReset}>
          Reset to Default
        </Button>
      )}
    </div>
  )
}
