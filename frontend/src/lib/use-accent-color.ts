import { resolveAccentTokens } from "./accent-contrast"
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

function apply(hex: string, theme?: 'dark' | 'light') {
  const root = document.documentElement
  const mode = theme ?? (root.classList.contains('light') ? 'light' : 'dark')
  const style = getComputedStyle(root)
  const surface = (name: string, fallback: string) => {
    const value = style.getPropertyValue(name).trim()
    return /^#[a-f0-9]{6}$/i.test(value) ? value : fallback
  }
  const tokens = resolveAccentTokens(hex, mode, {
    background: surface('--background', mode === 'light' ? '#f2f3ee' : '#08090a'),
    card: surface('--card', mode === 'light' ? '#ffffff' : '#101214'),
    accent: surface('--accent', mode === 'light' ? '#e7e8e2' : '#1b1d20'),
  })
  root.style.setProperty('--primary', tokens.primary)
  root.style.setProperty('--primary-foreground', tokens.primaryForeground)
  root.style.setProperty('--ring', tokens.ring)
  root.style.setProperty('--accent-foreground', tokens.accentForeground)
}
export function applyAccentForTheme(theme: 'dark' | 'light') {
  load()
  apply(current, theme)
}

let current = DEFAULT_HEX
let loaded = false
const listeners = new Set<() => void>()

function load() {
  if (loaded) return
  loaded = true
  try {
    const stored = preferenceStorage.getItem(STORAGE_KEY)
    if (stored && hexToHsv(stored)) current = hsvToHex(hexToHsv(stored)!)
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
  current = hsvToHex(hexToHsv(hex)!)
  apply(current)
  try {
    preferenceStorage.setItem(STORAGE_KEY, current)
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
