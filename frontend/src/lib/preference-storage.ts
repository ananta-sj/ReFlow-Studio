import { bridge } from './api'
import { withStartupTimeout } from './startup-timeout'

const keys = ['reflow-theme', 'reflow-experience-level', 'reflow.accentColor',
  'reflow.helpTooltipsEnabled', 'reflow.tourComplete', 'reflow.renderConfig', 'reflow.device']
let values: Record<string, string> = {}
let pending: Promise<unknown> = Promise.resolve()

function warn(error: unknown) {
  console.warn('UI preferences could not be persisted', error)
  window.__reflow?.dispatch('log', { level: 'warning', message: 'UI preferences could not be saved. Changes may be lost on restart.' })
}

export async function initializePreferences() {
  try {
    values = await withStartupTimeout(bridge.getUiPreferences(), 'Saved interface settings did not respond. Please retry.')
    // Migrate only app-owned keys from an existing browser session.
    const migration: Record<string, string> = {}
    for (const key of keys) {
      if (values[key] !== undefined) continue
      try {
        const old = localStorage.getItem(key)
        if (old !== null) migration[key] = old
      } catch { /* Session cache is optional. */ }
    }
    for (const [key, value] of Object.entries(migration)) {
      try { values = await withStartupTimeout(bridge.updateUiPreferences({ [key]: value }), 'Settings migration did not respond. Please retry.') }
      catch (error) { warn(error) }
    }
  } catch (error) {
    warn(error)
    throw new Error('Saved interface settings could not be loaded. Please retry before continuing.')
  }
}

export const preferenceStorage = {
  getItem(key: string): string | null { return values[key] ?? null },
  setItem(key: string, value: string) {
    if (!keys.includes(key)) throw new Error('Unknown UI preference')
    if (values[key] === value) return
    values[key] = value
    pending = pending.then(() => bridge.updateUiPreferences({ [key]: value })).catch(warn)
  },
}

export async function flushPreferences() { await pending }
