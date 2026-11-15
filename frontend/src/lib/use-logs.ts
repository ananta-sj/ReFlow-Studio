import { useSyncExternalStore } from 'react'
import { bridge } from './api'
import { subscribe } from './events'

export interface LogEntry {
  id: string
  time_ms: number
  level: 'info' | 'success' | 'warning' | 'error'
  message: string
}

let entries: LogEntry[] = []
let connected = false
let sequence = 0
const listeners = new Set<() => void>()

function merge(incoming: LogEntry[]) {
  const all = new Map(entries.map(entry => [entry.id, entry]))
  for (const entry of incoming) all.set(entry.id, entry)
  entries = [...all.values()].sort((a, b) => a.time_ms - b.time_ms).slice(-1000)
  listeners.forEach(listener => listener())
}

export function initializeLogs() {
  if (connected) return
  connected = true
  subscribe('log', payload => {
    const entry = payload as Partial<LogEntry>
    merge([{
      id: entry.id ?? `local-${Date.now()}-${++sequence}`,
      time_ms: entry.time_ms ?? Date.now(),
      level: entry.level ?? 'info',
      message: entry.message ?? '',
    }])
  })
  const refresh = async () => {
    try { merge(await bridge.getLogs()) } catch { /* Reconnect on the next poll. */ }
  }
  void refresh()
  setInterval(() => void refresh(), 5000)
}

function listen(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}
const snapshot = () => entries

export function useLogs() {
  return useSyncExternalStore(listen, snapshot, snapshot)
}
