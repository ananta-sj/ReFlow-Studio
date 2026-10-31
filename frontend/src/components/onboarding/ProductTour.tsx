// Renders the active tour step as a spotlight (a transparent cutout with
// a huge box-shadow dimming everything else - simpler and more robust
// than a clip-path mask) around the target element, plus a positioned
// callout with Back/Next/Skip. See lib/use-tour.ts for the step data and
// state machine.
import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { Button } from "@/components/ui/button"
import { endTour, nextTourStep, prevTourStep, useTour } from "@/lib/use-tour"
import type { PageId } from "@/components/shell/PrimaryNav"

interface ProductTourProps {
  currentPage: PageId
  onNavigate: (page: PageId) => void
}

export function ProductTour({ currentPage, onNavigate }: ProductTourProps) {
  const { active, stepIndex, step, totalSteps } = useTour()
  const [rect, setRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    if (!active || !step) return
    if (step.page && step.page !== currentPage) {
      onNavigate(step.page)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, stepIndex])

  useEffect(() => {
    if (!active || !step?.target) {
      setRect(null)
      return
    }
    // A page switch (or the very first render of a step) needs a beat for
    // the target's page to actually mount before it can be measured.
    let raf = 0
    const measure = () => {
      const el = document.querySelector(`[data-tour="${step.target}"]`)
      setRect(el ? el.getBoundingClientRect() : null)
    }
    const timeout = setTimeout(() => {
      measure()
      raf = requestAnimationFrame(measure)
    }, 80)
    window.addEventListener("resize", measure)
    return () => {
      clearTimeout(timeout)
      cancelAnimationFrame(raf)
      window.removeEventListener("resize", measure)
    }
  }, [active, stepIndex, step, currentPage])

  if (!active || !step) return null

  const pad = 8
  const spotlightStyle: React.CSSProperties = rect
    ? {
        position: "fixed",
        left: rect.left - pad,
        top: rect.top - pad,
        width: rect.width + pad * 2,
        height: rect.height + pad * 2,
        borderRadius: 10,
        boxShadow: "0 0 0 9999px rgba(5, 6, 7, 0.75)",
        pointerEvents: "none",
        zIndex: 100,
        transition: "left 0.25s ease, top 0.25s ease, width 0.25s ease, height 0.25s ease",
      }
    : {
        position: "fixed",
        inset: 0,
        background: "rgba(5, 6, 7, 0.75)",
        pointerEvents: "none",
        zIndex: 100,
      }

  // Callout: centered if there's no target, otherwise anchored just below
  // (or above, if there's no room below) the spotlighted rect.
  const calloutStyle: React.CSSProperties = rect
    ? {
        position: "fixed",
        left: Math.min(Math.max(16, rect.left), window.innerWidth - 336),
        top:
          rect.bottom + pad + 220 < window.innerHeight
            ? rect.bottom + pad + 12
            : Math.max(16, rect.top - pad - 12 - 200),
        zIndex: 101,
      }
    : {
        position: "fixed",
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
        zIndex: 101,
      }

  return (
    <AnimatePresence>
      <motion.div
        key={stepIndex}
        style={spotlightStyle}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      />
      <motion.div
        key={`callout-${stepIndex}`}
        style={calloutStyle}
        className="w-80 rounded-lg border border-border bg-card p-4 shadow-2xl"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.2 }}
      >
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Step {stepIndex + 1} / {totalSteps}
          </span>
          <button type="button" onClick={endTour} className="text-xs text-muted-foreground hover:text-foreground">
            Skip
          </button>
        </div>
        <h3 className="mb-1 text-sm font-bold" style={{ fontFamily: "var(--font-display)" }}>
          {step.title}
        </h3>
        <p className="mb-4 text-xs text-muted-foreground">{step.description}</p>
        <div className="flex items-center justify-between">
          {stepIndex > 0 ? (
            <Button variant="outline" size="sm" onClick={prevTourStep}>Back</Button>
          ) : (
            <span />
          )}
          <Button size="sm" onClick={nextTourStep}>
            {stepIndex === totalSteps - 1 ? "Finish" : "Next"}
          </Button>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
