import { useEffect, useSyncExternalStore } from 'react'
import { bridge, type JobActionResult } from './api'
import { subscribe } from './events'
import { createJobStore } from './job-store'

const store = createJobStore()
let connected = false
export function initializeJobs() {
  if (connected) return
  connected = true
  // Subscribe before hydration; revisions protect against delayed responses.
  subscribe('session_state', (payload) => store.apply(payload as Parameters<typeof store.apply>[0]))
  void refreshJobs()
  setInterval(() => { void refreshJobs() }, 5000)
}
export async function refreshJobs() {
  try { await store.refresh(bridge.getSessionState) } catch { /* retry next poll */ }
}
export function runJobAction(send: () => Promise<JobActionResult>) {
  initializeJobs()
  return store.act(send, bridge.getSessionState)
}
export function useJobs() {
  useEffect(initializeJobs, [])
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot)
}
