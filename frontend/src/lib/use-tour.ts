import { preferenceStorage } from "./preference-storage"
// First-run product tour state - a Figma/Photoshop-style spotlight
// walkthrough that highlights real UI elements (via data-tour="..."
// attributes) one at a time. Shown once automatically right after the
// SetupWizard finishes, and replayable anytime from Settings ("demo
// mode") via startTour(). Purely cosmetic frontend state (localStorage),
// same split as theme/experience-level/accent-color.
import { useEffect, useState } from "react"
import type { PageId } from "@/components/shell/PrimaryNav"

const STORAGE_KEY = "reflow.tourComplete"

export interface TourStep {
  target: string | null // data-tour value to spotlight, or null for a centered welcome/done card
  page?: PageId // navigates here before showing this step, if set
  title: string
  description: string
}

export const TOUR_STEPS: TourStep[] = [
  {
    target: null,
    title: "Welcome to Reflow Studio",
    description:
      "A quick tour of the essentials - translate, dub, and lip-sync video in a few clicks. Takes about a minute; skip anytime.",
  },
  {
    target: "nav-dashboard",
    page: "dashboard",
    title: "Dashboard",
    description: "Your main workspace - pick a video, choose a language and voice, and start a render from here.",
  },
  {
    target: "dashboard-source",
    page: "dashboard",
    title: "Source Input",
    description: "Select or drop in a video, audio file, or subtitle file here - the pipeline template adapts to what you pick.",
  },
  {
    target: "dashboard-estimate",
    page: "dashboard",
    title: "Render Estimate",
    description:
      "Shows how long the job would take on each of your devices, plus a projected system load - color-coded green/yellow/red so you can see at a glance if a device is a safe choice.",
  },
  {
    target: "initialize-pipeline",
    page: "dashboard",
    title: "Initialize Pipeline",
    description: "Starts the render with your current settings. If projected load is too high, this warns you before anything runs.",
  },
  {
    target: "experience-level",
    title: "Experience Level",
    description:
      "BASIC keeps things simple. ADVANCED unlocks the node graph and per-stage controls. EXPERT adds raw settings and engine-level configuration.",
  },
  {
    target: "nav-marketplace",
    title: "Marketplace",
    description: "Connect local models, cloud APIs, or local services for every pipeline stage - or pick from curated recommendations.",
  },
  {
    target: "nav-settings",
    title: "Settings",
    description:
      "Defaults, the accent color picker, and this tour's replay button all live here - look for \"Replay Tour\" anytime you want to see this again.",
  },
  {
    target: null,
    title: "You're all set",
    description: "That's the tour. Everything here is also explained by the \"?\" icons throughout the app if you want more detail.",
  },
]

let active = false
let stepIndex = 0
const listeners = new Set<() => void>()

function notify() {
  listeners.forEach((fn) => fn())
}

export function hasTourCompleted(): boolean {
  try {
    return preferenceStorage.getItem(STORAGE_KEY) === "true"
  } catch {
    return true // fail closed - don't nag if storage is unavailable
  }
}

export function startTour() {
  active = true
  stepIndex = 0
  notify()
}

export function endTour() {
  active = false
  try {
    preferenceStorage.setItem(STORAGE_KEY, "true")
  } catch {
    // non-fatal - worst case the tour offers to run again next launch
  }
  notify()
}

export function nextTourStep() {
  if (stepIndex >= TOUR_STEPS.length - 1) {
    endTour()
    return
  }
  stepIndex += 1
  notify()
}

export function prevTourStep() {
  stepIndex = Math.max(0, stepIndex - 1)
  notify()
}

export function useTour() {
  const [, forceRender] = useState(0)
  useEffect(() => {
    const fn = () => forceRender((t) => t + 1)
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  }, [])
  return { active, stepIndex, step: TOUR_STEPS[stepIndex], totalSteps: TOUR_STEPS.length }
}
