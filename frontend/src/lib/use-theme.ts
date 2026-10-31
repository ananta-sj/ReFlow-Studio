import { preferenceStorage } from "./preference-storage"
import { useEffect, useState } from "react"

export type Theme = "dark" | "light"
const STORAGE_KEY = "reflow-theme"

function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.remove("dark", "light")
  root.classList.add(theme)
}

function getInitialTheme(): Theme {
  const stored = preferenceStorage.getItem(STORAGE_KEY)
  return stored === "light" ? "light" : "dark"
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    applyTheme(theme)
    preferenceStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  function toggle() {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"))
  }

  return { theme, toggle }
}
