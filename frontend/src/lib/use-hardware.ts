import { useEffect, useRef, useState } from "react"
import { bridge, type HardwareSnapshot } from "@/lib/api"

const MAX_HISTORY = 30

export interface HardwarePoint {
  date: Date
  cpu: number
  [key: string]: unknown
}

export function useHardware(selectedDeviceId: string | null) {
  const [snapshot, setSnapshot] = useState<HardwareSnapshot | null>(null)
  const [history, setHistory] = useState<HardwarePoint[]>([])
  const historyRef = useRef<HardwarePoint[]>([])

  useEffect(() => {
    let cancelled = false

    async function tick() {
      try {
        const snap = await bridge.getHardwareSnapshot(selectedDeviceId ?? undefined)
        if (cancelled) return
        setSnapshot(snap)
        const next = [...historyRef.current, { date: new Date(), cpu: snap.cpu_percent }].slice(-MAX_HISTORY)
        historyRef.current = next
        setHistory(next)
      } catch {
        // pywebview not ready yet on the very first tick - next interval retries
      }
    }

    tick()
    const id = setInterval(tick, 2000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [selectedDeviceId])

  return { snapshot, history }
}
