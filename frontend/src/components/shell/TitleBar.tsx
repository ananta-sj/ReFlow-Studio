import { useRef, useState } from "react"
import { withStartupTimeout } from "@/lib/startup-timeout"
import { Minus, Radio, Square, X, TerminalSquare, Sun, Moon } from "lucide-react"
import { bridge } from "@/lib/api"
import { HelpTooltip } from "@/components/shared/HelpTooltip"
import { confirmAction } from "@/lib/use-confirm"
import { useRenderJob } from "@/lib/use-render"
import type { PageId } from "@/components/shell/PrimaryNav"
import type { Theme } from "@/lib/use-theme"

interface TitleBarProps {
  onNavigate: (page: PageId) => void
  theme: Theme
  onToggleTheme: () => void
}

function IconBtn({ children, onClick, label, danger }: { children: React.ReactNode; onClick: () => void; label: string; danger?: boolean }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary flex h-7 w-7 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground ${danger ? "hover:bg-destructive hover:text-destructive-foreground" : ""}`}
    >
      {children}
    </button>
  )
}

export function TitleBar({ onNavigate, theme, onToggleTheme }: TitleBarProps) {
  const render = useRenderJob()
  const closingRef = useRef(false)
  const [closing, setClosing] = useState(false)

  async function handleClose() {
    if (closingRef.current) return
    closingRef.current = true
    setClosing(true)
    let requested = false
    try {
      const settings = await withStartupTimeout(bridge.getSettings(), "Close settings did not respond.")
      const cleanup = settings.values.clear_temp_on_exit
        ? ' Temporary working files will be cleared on exit. Saved recovery files remain available.'
        : ' Temporary working files will be kept according to your cleanup settings.'
      const ok = await confirmAction({
        title: "Close Reflow Studio?",
        description: render.isRunning
          ? "ReFlow will pause the current job. On reopening, Resume can reuse completed work." + cleanup
          : "Close ReFlow Studio?" + cleanup,
        confirmLabel: "Close",
        destructive: render.isRunning,
      })
      if (!ok) return
      await bridge.closeWindow()
      requested = true
    } catch {
      await confirmAction({ title: "Close unavailable",
        description: "ReFlow could not complete the close request. Please retry. Your cleanup and recovery settings have not been bypassed.", alertOnly: true })
    } finally {
      if (!requested) { closingRef.current = false; setClosing(false) }
    }
  }

  return (
    <div className="pywebview-drag-region flex h-10 shrink-0 items-center justify-between border-b border-border bg-background px-3">
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-primary shadow-[0_0_10px_var(--primary)]" />
        <span
          className="text-base font-bold tracking-wide"
          style={{ fontFamily: "var(--font-display)" }}
        >
          <span className="text-foreground">REFLOW</span>{" "}
          <span className="text-primary drop-shadow-[0_0_6px_var(--primary)]">STUDIO</span>
        </span>
      </div>

      <div className="flex items-center gap-1">
        <IconBtn label="Open logs" onClick={() => onNavigate("logs")}>
          <TerminalSquare className="h-4 w-4" />
        </IconBtn>
        <IconBtn label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} onClick={onToggleTheme}>
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </IconBtn>

        <div className="mx-1 h-4 w-px bg-border" />

        <div className="flex items-center gap-1">
          <IconBtn label="Minimize to tray" onClick={() => bridge.minimizeToTray()}>
            <Radio className="h-4 w-4" />
          </IconBtn>
          <HelpTooltip text="Hides the window completely (no taskbar entry) and keeps running in the background - a render in progress isn't affected. Click the tray icon to bring it back." />
        </div>

        <button
          type="button"
          aria-label="Minimize window"
          title="Minimize window"
          onClick={() => bridge.minimizeWindow()}
          className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label="Maximize or restore window"
          title="Maximize or restore window"
          onClick={() => bridge.toggleMaximizeWindow()}
          className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Square className="h-3 w-3" />
        </button>
        <button
          type="button"
          aria-label="Close window"
          title={closing ? "Closing…" : "Close window"}
          disabled={closing}
          aria-busy={closing}
          onClick={handleClose}
          className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-destructive hover:text-destructive-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
