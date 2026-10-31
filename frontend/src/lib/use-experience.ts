import { preferenceStorage } from "./preference-storage"
import { useEffect, useState } from "react"

export type ExperienceLevel = "basic" | "advanced" | "expert"
const STORAGE_KEY = "reflow-experience-level"
const LEVELS: ExperienceLevel[] = ["basic", "advanced", "expert"]

function getInitial(): ExperienceLevel {
  const stored = preferenceStorage.getItem(STORAGE_KEY)
  return LEVELS.includes(stored as ExperienceLevel) ? (stored as ExperienceLevel) : "basic"
}

/** Ordinal comparison helper - e.g. atLeast("advanced") is true for both
 * "advanced" and "expert", false for "basic". Used everywhere content is
 * gated by level so "expert" doesn't have to duplicate "advanced" checks. */
export function levelAtLeast(current: ExperienceLevel, min: ExperienceLevel) {
  return LEVELS.indexOf(current) >= LEVELS.indexOf(min)
}

export function useExperienceLevel() {
  const [level, setLevel] = useState<ExperienceLevel>(getInitial)

  useEffect(() => {
    preferenceStorage.setItem(STORAGE_KEY, level)
  }, [level])

  return { level, setLevel }
}
