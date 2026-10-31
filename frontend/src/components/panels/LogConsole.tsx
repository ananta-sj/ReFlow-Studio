import { useEffect, useRef, useState } from "react"
import { subscribe } from "@/lib/events"
import { cn } from "@/lib/utils"

interface LogEntry {
  id: number
  time: string
  level: "info" | "success" | "warning" | "error"
  message: string
}

const LEVEL_COLOR: Record<LogEntry["level"], string> = {
  info: "text-primary",
  success: "text-success",
  warning: "text-warning",
  error: "text-destructive",
}

const TAG_COLOR: Record<string, string> = {
  CORE: "text-secondary",
  QUEUE: "text-secondary",
  PHASE: "text-primary",
  GPU: "text-success",
  NEURAL: "text-[#B08CF0]",
  PIPELINE: "text-secondary",
  DATA: "text-[#4FD0C0]",
  SHADER: "text-[#E06FC4]",
  GEOMETRY: "text-[#E0954C]",
  STOP: "text-destructive",
}

let nextId = 1

function renderMessage(message: string) {
  const match = message.match(/^(\[[A-Z_]+\])(\s*.*)$/)
  if (!match) return <>{message}</>
  const [, tag, rest] = match
  const tagName = tag.slice(1, -1)
  return (
    <>
      <span className={TAG_COLOR[tagName] ?? "text-muted-foreground"}>{tag}</span>
      {rest}
    </>
  )
}

export function LogConsole({ className }: { className?: string }) {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return subscribe("log", (payload) => {
      const { level = "info", message = "" } = (payload ?? {}) as { level?: LogEntry["level"]; message?: string }
      setEntries((prev) => [
        ...prev,
        { id: nextId++, time: new Date().toLocaleTimeString(), level, message },
      ].slice(-300))
    })
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" })
  }, [entries])

  return (
    <div
      className={cn(
        "overflow-y-auto rounded-md border border-border bg-background p-2 font-mono text-[11px] leading-5",
        className
      )}
    >
      {entries.length === 0 && <div className="text-muted-foreground">Waiting for activity…</div>}
      {entries.map((entry) => (
        <div key={entry.id}>
          <span className="text-muted-foreground/60">[{entry.time}] </span>
          <span className={LEVEL_COLOR[entry.level]}>{renderMessage(entry.message)}</span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

export function pushLocalLog(level: LogEntry["level"], message: string) {
  // For UI-originated events (not from Python) that should still appear in
  // the console, e.g. "Switched to ADVANCED view."
  window.__reflow.dispatch("log", { level, message })
}
