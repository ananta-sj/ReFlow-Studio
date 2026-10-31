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

function IconBtn({ children, onClick, danger }: { children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex h-7 w-7 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground ${danger ? "hover:bg-destructive hover:text-destructive-foreground" : ""}`}
    >
      {children}
    </button>
  )
}

export function TitleBar({ onNavigate, theme, onToggleTheme }: TitleBarProps) {
  const render = useRenderJob()

  async function handleClose() {
    const ok = await confirmAction({
      title: "Close Reflow Studio?",
      description: render.isRunning
        ? "A render is currently in progress. Closing now will stop it, and any progress on the current job will be lost."
        : "Are you sure you want to close the app?",
      confirmLabel: "Close",
      destructive: render.isRunning,
    })
    if (!ok) return
    bridge.closeWindow()
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
        <IconBtn onClick={() => onNavigate("logs")}>
          <TerminalSquare className="h-4 w-4" />
        </IconBtn>
        <IconBtn onClick={onToggleTheme}>
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </IconBtn>

        <div className="mx-1 h-4 w-px bg-border" />

        <div className="flex items-center gap-1">
          <IconBtn onClick={() => bridge.minimizeToTray()}>
            <Radio className="h-4 w-4" />
          </IconBtn>
          <HelpTooltip text="Hides the window completely (no taskbar entry) and keeps running in the background - a render in progress isn't affected. Click the tray icon to bring it back." />
        </div>

        <button
          type="button"
          onClick={() => bridge.minimizeWindow()}
          className="flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={() => bridge.toggleMaximizeWindow()}
          className="flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Square className="h-3 w-3" />
        </button>
        <button
          type="button"
          onClick={handleClose}
          className="flex h-6 w-8 items-center justify-center rounded text-muted-foreground hover:bg-destructive hover:text-destructive-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
