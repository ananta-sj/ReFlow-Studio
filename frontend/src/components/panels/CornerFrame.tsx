import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

const CORNER = "absolute h-3 w-3"

interface CornerFrameProps {
  children: ReactNode
  className?: string
  dim?: boolean
}

export function CornerFrame({ children, className, dim }: CornerFrameProps) {
  const color = dim ? "border-border" : "border-primary/70"
  return (
    <div className={cn("relative", className)}>
      <span className={cn(CORNER, color, "top-0 left-0 border-t-2 border-l-2")} />
      <span className={cn(CORNER, color, "top-0 right-0 border-t-2 border-r-2")} />
      <span className={cn(CORNER, color, "bottom-0 left-0 border-b-2 border-l-2")} />
      <span className={cn(CORNER, color, "bottom-0 right-0 border-b-2 border-r-2")} />
      {children}
    </div>
  )
}
