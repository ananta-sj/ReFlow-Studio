import { cn } from "@/lib/utils"
import { levelAtLeast, type ExperienceLevel } from "@/lib/use-experience"

export type PageId = "dashboard" | "nodes" | "assets" | "marketplace" | "logs" | "settings"

const NAV_ITEMS: { id: PageId; label: string; minLevel?: ExperienceLevel }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "nodes", label: "Nodes", minLevel: "advanced" },
  { id: "assets", label: "Assets" },
  { id: "marketplace", label: "Marketplace" },
  { id: "logs", label: "Logs" },
  { id: "settings", label: "Settings" },
]

const LEVEL_OPTIONS: { id: ExperienceLevel; label: string }[] = [
  { id: "basic", label: "BASIC" },
  { id: "advanced", label: "ADVANCED" },
  { id: "expert", label: "EXPERT" },
]

interface PrimaryNavProps {
  activePage: PageId
  onNavigate: (page: PageId) => void
  level: ExperienceLevel
  onLevelChange: (level: ExperienceLevel) => void
  online: boolean
}

export function PrimaryNav({ activePage, onNavigate, level, onLevelChange, online }: PrimaryNavProps) {
  return (
    <div className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-background px-4">
      <nav className="flex items-center gap-1">
        {NAV_ITEMS.filter((item) => !item.minLevel || levelAtLeast(level, item.minLevel)).map((item) => (
          <button
            key={item.id}
            type="button"
            data-tour={`nav-${item.id}`}
            onClick={() => onNavigate(item.id)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              activePage === item.id
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        {/* Experience level: how much of the app's settings/features are
            disclosed - a content-density preference, not a navigation
            control (the tabs above are for that). */}
        <div className="flex items-center rounded-md border border-border p-0.5" title="Experience level" data-tour="experience-level">
          {LEVEL_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => onLevelChange(opt.id)}
              className={cn(
                "rounded px-2.5 py-1 text-xs font-semibold tracking-wide",
                level === opt.id ? "bg-primary text-primary-foreground" : "text-muted-foreground"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div
          className="flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs"
          style={{ fontFamily: "var(--font-mono)" }}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              online ? "bg-success shadow-[0_0_6px_var(--success)]" : "bg-destructive"
            )}
          />
          <span className="text-muted-foreground">
            01 // CORE: {online ? "OPERATIONAL" : "OFFLINE"}
          </span>
        </div>
      </div>
    </div>
  )
}
