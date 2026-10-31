// Python -> JS push channel. bridge/push.py calls
// `window.__reflow.dispatch(eventName, payload)` via evaluate_js(); this
// fans that out to whichever React components have subscribed, mirroring
// what the old PyQt build's progress_signal/log_signal/stage_signal did.

type Listener = (payload: unknown) => void

const listeners = new Map<string, Set<Listener>>()

function dispatch(eventName: string, payload: unknown) {
  listeners.get(eventName)?.forEach((fn) => fn(payload))
}

export function subscribe(eventName: string, fn: Listener) {
  if (!listeners.has(eventName)) listeners.set(eventName, new Set())
  listeners.get(eventName)!.add(fn)
  return () => {
    listeners.get(eventName)?.delete(fn)
  }
}

declare global {
  interface Window {
    __reflow: { dispatch: typeof dispatch }
  }
}

window.__reflow = { dispatch }
