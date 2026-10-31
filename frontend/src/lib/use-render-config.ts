import { preferenceStorage } from "./preference-storage"
// Shared render configuration (template/lang/voice/toggles/priority/etc) -
// used by both Dashboard and Nodes so they never show two different
// answers for "is Lip Sync on" (the same class of bug this session
// already fixed once before, when a separate Basic/Advanced toggle
// duplicated the Nodes nav tab). Also persisted through the app-owned preference store so a
// render configuration survives an app restart instead of silently
// resetting to the saved defaults every time - "remember what I had
// selected last time," not just "remember the factory default."
import { useEffect, useState } from "react"
import { bridge, type PipelineTemplateId } from "@/lib/api"

export interface RenderConfig {
  template: PipelineTemplateId
  lang: string
  sourceLanguage: string
  voice: string
  refAudio: string | null
  keepBg: boolean
  lipsync: boolean
  enhance: boolean
  burnSubs: boolean
  contentFilter: boolean
  taskPriority: number
  qualityIdx: number
  parallelWorkers: number
  includeSubtitles: boolean
  exportStems: boolean
  subtitleFontSize: number
}

export const QUALITY_STEPS = [1, 2, 4]

const STORAGE_KEY = "reflow.renderConfig"

// The stages that have both a Dashboard toggle AND a real graph node
// backing the exact same pipeline behavior - the single mapping both this
// module (writing) and Nodes.tsx (reading) use, so they can't drift apart.
export const STAGE_NODE_MAP: Record<string, keyof RenderConfig> = {
  separate: "keepBg",
  lipsync: "lipsync",
  enhance: "enhance",
  content_filter: "contentFilter",
  subtitles: "includeSubtitles",
}

let config: RenderConfig = {
  template: "video_dub",
  lang: "en",
  sourceLanguage: "auto",
  voice: "CLONED_USER",
  refAudio: null,
  keepBg: true,
  lipsync: false,
  enhance: false,
  burnSubs: false,
  contentFilter: false,
  taskPriority: 75,
  qualityIdx: 0,
  parallelWorkers: 1,
  includeSubtitles: true,
  exportStems: false,
  subtitleFontSize: 24,
}
let loaded = false
const listeners = new Set<() => void>()

function persist() {
  try {
    preferenceStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch {
    // Losing "remember my last settings" isn't worth crashing over.
  }
}

function notify() {
  listeners.forEach((fn) => fn())
  persist()
}

function readStoredConfig(): Partial<RenderConfig> | null {
  try {
    const raw = preferenceStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function updateConfig(partial: Partial<RenderConfig>) {
  config = { ...config, ...partial }
  notify()
  for (const [nodeId, key] of Object.entries(STAGE_NODE_MAP)) {
    if (key in partial) syncStageFlag(nodeId, partial[key as keyof RenderConfig] as boolean)
  }
}

function syncStageFlag(nodeId: string, enabled: boolean) {
  // Render flags own future-job selection; accepted jobs retain their snapshot.
  // The saved graph mirror may reject an edit during active work or publication.
  // Report that failure without discarding the user's future render choice.
  const warn = (detail: string) => {
    const message = `Graph switch ${nodeId} could not be saved: ${detail}. The render setting is retained for new jobs.`
    console.warn(message)
    window.__reflow?.dispatch('log', { level: 'warning', message })
  }
  bridge.setNodeEnabled(nodeId, enabled).then(result => {
    if (!result.ok) warn(result.message ?? 'The change was rejected')
  }).catch(error => warn(String(error)))
}

/** Nodes.tsx calls this when a node switch is flipped directly on the
 * graph, so it updates the shared config (and therefore Dashboard) without
 * re-triggering a redundant setNodeEnabled call back at the node it came
 * from. */
export function setStageFromNode(nodeId: string, enabled: boolean) {
  const key = STAGE_NODE_MAP[nodeId]
  if (!key) return
  config = { ...config, [key]: enabled }
  listeners.forEach((fn) => fn())
  persist()
}

export async function loadConfigDefaults() {
  if (loaded) return
  loaded = true

  const stored = readStoredConfig()
  if (stored) {
    config = { ...config, ...stored,
      sourceLanguage: typeof stored.sourceLanguage === "string" && stored.sourceLanguage.trim()
        ? stored.sourceLanguage : "auto" }
  } else {
    // First ever run on this machine - seed from the persisted app
    // defaults (core/settings.py) instead of this module's hardcoded
    // fallbacks.
    const { values } = await bridge.getSettings()
    config = {
      ...config,
      lang: values.default_language,
      voice: values.default_voice,
      keepBg: values.keep_bg_default,
      contentFilter: values.content_filter_default,
      taskPriority: values.default_task_priority,
      qualityIdx: Math.max(0, QUALITY_STEPS.indexOf(values.default_texture_quality)),
    }
  }

  // Dashboard owns the optional-stage switches. Restore those into the
  // graph; its saved layout and additional cast choices remain independent.
  for (const [nodeId, key] of Object.entries(STAGE_NODE_MAP)) {
    syncStageFlag(nodeId, config[key] as boolean)
  }

  notify()
}

export function useRenderConfig() {
  const [state, setState] = useState(config)
  useEffect(() => {
    const listener = () => setState(config)
    listeners.add(listener)
    loadConfigDefaults().catch(error => {
      loaded = false
      console.warn('Render preferences could not be restored', error)
    })
    return () => {
      listeners.delete(listener)
    }
  }, [])
  return state
}
