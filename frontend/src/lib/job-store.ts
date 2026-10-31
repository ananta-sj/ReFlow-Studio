import type { SessionSnapshot, JobActionResult } from './api'
import { INITIAL } from './render-state'

// One store lives independently of page mounts. Transport injection allows
// regression checks to exercise the same store logic used by the app.
export function createJobStore() {
  let state: SessionSnapshot = { sessionId: '', revision: -1, render: INITIAL,
    queue: [], busy: false, paused: false, lastEventAt: 0 }
  const listeners = new Set<() => void>()
  const retiredSessions = new Set<string>()
  let epoch = 0
  const notify = () => listeners.forEach((fn) => fn())
  function apply(snapshot: SessionSnapshot, fromRequest = false, requestEpoch = epoch) {
    if (fromRequest && requestEpoch !== epoch && snapshot.sessionId !== state.sessionId) return
    if (retiredSessions.has(snapshot.sessionId)) return
    if (snapshot.sessionId === state.sessionId && snapshot.revision < state.revision) return
    if (snapshot.sessionId !== state.sessionId && state.sessionId) retiredSessions.add(state.sessionId)
    state = snapshot
    epoch++
    notify()
  }
  async function refresh(read: () => Promise<SessionSnapshot>) {
    const at = epoch
    apply(await read(), true, at)
  }
  async function act(send: () => Promise<JobActionResult>, read: () => Promise<SessionSnapshot>) {
    let result: JobActionResult
    try { result = await send() }
    catch (error) { result = { ok: false, message: String(error) } }
    try { await refresh(read) } catch { /* retain state during reconnect */ }
    return result
  }
  return { getSnapshot: () => state, apply, refresh, act,
    subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn) } } }
}
