// The small "?" icon shown next to labels for anything that can be
// enabled/disabled/inserted/modified - hover (or tap) reveals a short
// plain-language explanation of what the control actually does. Renders
// nothing at all when the user has turned help tooltips off in Settings
// (see lib/use-help-tooltips.ts), rather than just visually hiding it, so
// disabling it also removes it from tab order/screen readers.
import { HelpCircle } from "lucide-react"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useHelpTooltipsEnabled } from "@/lib/use-help-tooltips"
import { cn } from "@/lib/utils"

export function HelpTooltip({ text, className }: { text: string; className?: string }) {
  const enabled = useHelpTooltipsEnabled()
  if (!enabled) return null

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={(e) => e.preventDefault()}
          className={cn(
            "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-muted-foreground/20 text-muted-foreground transition-colors hover:bg-muted-foreground/30 hover:text-foreground",
            className
          )}
          aria-label="Help"
        >
          <HelpCircle className="h-3 w-3" />
        </button>
      </TooltipTrigger>
      <TooltipContent>{text}</TooltipContent>
    </Tooltip>
  )
}
