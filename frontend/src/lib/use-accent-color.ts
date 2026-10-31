import { preferenceStorage } from "./preference-storage"
// Custom accent color override - a purely cosmetic frontend preference
// (localStorage, same split as theme/experience-level - see
// core/settings.py's own docstring on what belongs in settings.json vs
// localStorage). Overrides --primary (and everything derived from it -
// --ring, --accent-foreground, every shadow/glow that references
// var(--primary)) by setting the CSS custom property directly on
// :root, which cascades to all of them automatically since they're all
// var(--primary) references, not separately hardcoded colors.
import { useEffect, useState } from "react"

const STORAGE_KEY = "reflow.accentColor"
const DEFAULT_HEX = "#c8ff4d" // matches index.css's --primary default

export interface HSV {
  h: number // 0-360
  s: number // 0-100
  v: number // 0-100
}

export function hsvToHex({ h, s, v }: HSV): string {
  const sN = s / 100
  const vN = v / 100
  const c = vN * sN
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = vN - c
  let [r, g, b] = [0, 0, 0]
  if (h < 60) [r, g, b] = [c, x, 0]
  else if (h < 120) [r, g, b] = [x, c, 0]
  else if (h < 180) [r, g, b] = [0, c, x]
  else if (h < 240) [r, g, b] = [0, x, c]
  else if (h < 300) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]
  const toHex = (n: number) =>
    Math.round((n + m) * 255).toString(16).padStart(2, "0")
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

export function hexToHsv(hex: string): HSV | null {
  const match = /^#?([a-f\d]{6})$/i.exec(hex.trim())
  if (!match) return null
  const int = parseInt(match[1], 16)
  const r = ((int >> 16) & 255) / 255
  const g = ((int >> 8) & 255) / 255
  const b = (int & 255) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  let h = 0
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6
    else if (max === g) h = (b - r) / d + 2
    else h = (r - g) / d + 4
    h *= 60
    if (h < 0) h += 360
  }
  const s = max === 0 ? 0 : (d / max) * 100
  const v = max * 100
  return { h, s, v }
}

// Foreground text sitting on top of --primary needs to flip between near-
// black and near-white depending on the chosen color's perceived
// brightness, or a dark pick (e.g. deep blue) would render invisible text.
function bestForegroundFor(hex: string): string {
  const hsv = hexToHsv(hex)
  if (!hsv) return "#08090a"
  const { h, s, v } = hsv
  // Relative luminance approximation via the same HSV->RGB path.
  const [r, g, b] = (() => {
    const hex2 = hsvToHex({ h, s, v })
    const int = parseInt(hex2.slice(1), 16)
    return [(int >> 16) & 255, (int >> 8) & 255, int & 255]
  })()
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return luminance > 0.6 ? "#08090a" : "#f5f6f3"
}

function apply(hex: string) {
  const root = document.documentElement
  root.style.setProperty("--primary", hex)
  root.style.setProperty("--primary-foreground", bestForegroundFor(hex))
  root.style.setProperty("--ring", hex)
  root.style.setProperty("--accent-foreground", hex)
}

let current = DEFAULT_HEX
let loaded = false
const listeners = new Set<() => void>()

function load() {
  if (loaded) return
  loaded = true
  try {
    const stored = preferenceStorage.getItem(STORAGE_KEY)
    if (stored && hexToHsv(stored)) current = stored
  } catch {
    // default stands
  }
  apply(current)
}

function notify() {
  listeners.forEach((fn) => fn())
}

export function setAccentColor(hex: string) {
  load()
  if (!hexToHsv(hex)) return
  current = hex
  apply(hex)
  try {
    preferenceStorage.setItem(STORAGE_KEY, hex)
  } catch {
    // non-fatal - just won't survive a restart
  }
  notify()
}

export function resetAccentColor() {
  setAccentColor(DEFAULT_HEX)
}

export function getAccentColor() {
  load()
  return current
}

export function useAccentColor() {
  load()
  const [, forceRender] = useState(0)
  useEffect(() => {
    const fn = () => forceRender((t) => t + 1)
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  }, [])
  return { color: current, defaultColor: DEFAULT_HEX }
}
