import { preferenceStorage } from "./preference-storage"
// Global on/off switch for the "?" HelpTooltip icons (see
// components/shared/HelpTooltip.tsx) - a purely cosmetic frontend
// preference, so it lives in localStorage rather than settings.json (see
// core/settings.py's own docstring on that split). Same shared-module-state
// + subscriber pattern as lib/use-render-config.ts, since many HelpTooltip
// instances can be mounted across a page at once and all need to react
// immediately when the Settings page flips this.
import { useEffect, useState } from "react"

const STORAGE_KEY = "reflow.helpTooltipsEnabled"

let enabled = true
let loaded = false
const listeners = new Set<() => void>()

function load() {
  if (loaded) return
  loaded = true
  try {
    const raw = preferenceStorage.getItem(STORAGE_KEY)
    if (raw != null) enabled = raw === "true"
  } catch {
    // default (enabled) stands
  }
}

function notify() {
  listeners.forEach((fn) => fn())
}

export function setHelpTooltipsEnabled(next: boolean) {
  load()
  enabled = next
  try {
    preferenceStorage.setItem(STORAGE_KEY, String(next))
  } catch {
    // non-fatal - just won't survive a restart
  }
  notify()
}

export function getHelpTooltipsEnabled() {
  load()
  return enabled
}

export function useHelpTooltipsEnabled() {
  load()
  const [, forceRender] = useState(0)
  useEffect(() => {
    const fn = () => forceRender((t) => t + 1)
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  }, [])
  return enabled
}
