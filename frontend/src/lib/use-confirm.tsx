// Imperative confirmation dialog - call confirmAction({...}) from anywhere
// (a click handler, a settings patch, the window close button) and await
// the boolean result, instead of every call site owning its own Dialog
// open-state boilerplate. Same shared-module-state + subscriber pattern as
// lib/use-render-config.ts; only one confirmation can be pending at a time,
// which matches how it's actually used (a single user action at a time).
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"

export interface ConfirmOptions {
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  /** Renders a single acknowledgement button instead of Confirm/Cancel -
   * for blocking situations where there's no real choice to make (e.g.
   * projected load too high to safely start a render). Always resolves
   * false, so callers should never gate a proceed-path on the result. */
  alertOnly?: boolean
}

interface PendingConfirm extends ConfirmOptions {
  resolve: (choice: ConfirmChoice) => void
}

export type ConfirmChoice = 'confirm' | 'cancel' | 'dismiss'

let pending: PendingConfirm | null = null
const listeners = new Set<() => void>()
function notify() {
  listeners.forEach((fn) => fn())
}

/** Resolves true if the user confirms, false if they cancel or dismiss
 * (Escape, clicking outside, the X button) - always await it and bail out
 * on false, never assume confirmation just because nothing threw. */
export function confirmAction(options: ConfirmOptions): Promise<boolean> {
  return confirmChoice(options).then(choice => choice === 'confirm')
}

/** Distinguishes an explicit cancel button from closing the dialog. Use when
 * cancelling carries a side effect, such as discarding a recovery record. */
export function confirmChoice(options: ConfirmOptions): Promise<ConfirmChoice> {
  return new Promise((resolve) => {
    pending = { ...options, resolve }
    notify()
  })
}

function usePendingConfirm() {
  const [, forceRender] = useState(0)
  useEffect(() => {
    const fn = () => forceRender((t) => t + 1)
    listeners.add(fn)
    return () => {
      listeners.delete(fn)
    }
  }, [])
  return pending
}

/** Mounted once near the app root (see App.tsx) - renders nothing until
 * some other part of the app calls confirmAction(). */
export function ConfirmDialogHost() {
  const current = usePendingConfirm()

  function answer(choice: ConfirmChoice) {
    current?.resolve(choice)
    pending = null
    notify()
  }

  return (
    <Dialog open={current != null} onOpenChange={(open) => { if (!open) answer('dismiss') }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{current?.title}</DialogTitle>
          <DialogDescription className="max-h-72 overflow-auto whitespace-pre-wrap break-words">{current?.description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          {!current?.alertOnly && (
            <Button variant="outline" onClick={() => answer('cancel')}>
              {current?.cancelLabel ?? "Cancel"}
            </Button>
          )}
          <Button variant={current?.destructive ? "destructive" : "default"} onClick={() => answer(current?.alertOnly ? 'dismiss' : 'confirm')}>
            {current?.confirmLabel ?? (current?.alertOnly ? "OK" : "Confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
