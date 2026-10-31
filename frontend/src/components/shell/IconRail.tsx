import { LayoutDashboard, Workflow, FolderOpen, ScrollText, Settings, Store } from "lucide-react"
import { cn } from "@/lib/utils"
import { levelAtLeast, type ExperienceLevel } from "@/lib/use-experience"
import type { PageId } from "@/components/shell/PrimaryNav"

const RAIL_ITEMS: { id: PageId; icon: typeof LayoutDashboard; minLevel?: ExperienceLevel }[] = [
  { id: "dashboard", icon: LayoutDashboard },
  { id: "nodes", icon: Workflow, minLevel: "advanced" },
  { id: "assets", icon: FolderOpen },
  { id: "marketplace", icon: Store },
  { id: "logs", icon: ScrollText },
  { id: "settings", icon: Settings },
]

interface IconRailProps {
  activePage: PageId
  onNavigate: (page: PageId) => void
  level: ExperienceLevel
}

export function IconRail({ activePage, onNavigate, level }: IconRailProps) {
  return (
    <div className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-border bg-background py-3">
      {RAIL_ITEMS.filter((item) => !item.minLevel || levelAtLeast(level, item.minLevel)).map(({ id, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onNavigate(id)}
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-md transition-colors",
            activePage === id
              ? "bg-primary text-primary-foreground shadow-[0_0_12px_var(--primary)]"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          )}
        >
          <Icon className="h-5 w-5" />
        </button>
      ))}
    </div>
  )
}
