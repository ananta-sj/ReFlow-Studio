import { LogConsole } from "@/components/panels/LogConsole"

export function LogsPage() {
  return (
    <div className="flex h-full flex-col gap-3 p-6">
      <h2 className="text-sm font-semibold tracking-wide text-muted-foreground">01 // SYSTEM LOG</h2>
      <LogConsole className="flex-1 text-xs" />
    </div>
  )
}
