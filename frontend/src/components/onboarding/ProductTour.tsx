// Renders the active tour step as a spotlight (a transparent cutout with
// a huge box-shadow dimming everything else - simpler and more robust
// than a clip-path mask) around the target element, plus a positioned
// callout with Back/Next/Skip. See lib/use-tour.ts for the step data and
// state machine.
import { useCallback, useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { Button } from "@/components/ui/button"
import { endTour, nextTourStep, prevTourStep, useTour } from "@/lib/use-tour"
import { computeTourCallout } from "@/lib/tour-layout"
import type { PageId } from "@/components/shell/PrimaryNav"

interface ProductTourProps {
  currentPage: PageId
  onNavigate: (page: PageId) => void
}

export function ProductTour({ currentPage, onNavigate }: ProductTourProps) {
  const { active, stepIndex, step, totalSteps } = useTour()
  const [rect, setRect] = useState<DOMRect | null>(null)
  const calloutRef = useRef<HTMLDivElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  const [viewport, setViewport] = useState({ width: window.innerWidth, height: window.innerHeight })
  const [size, setSize] = useState({ width: 320, height: 240 })
  const currentPageRef = useRef(currentPage)
  const returnPage = useRef(currentPage)
  const [pendingFocusPage, setPendingFocusPage] = useState<PageId | null>(null)
  useEffect(() => { currentPageRef.current = currentPage }, [currentPage])
  const restoreFocus = useCallback(() => {
    const el = returnFocus.current
    returnFocus.current = null
    if (!el) return
    if (el.isConnected && el !== document.body) el.focus()
    else {
      onNavigate(returnPage.current)
      setPendingFocusPage(returnPage.current)
    }
  }, [onNavigate])
  useEffect(() => {
    if (active || !pendingFocusPage || currentPage !== pendingFocusPage) return
    const opener = pendingFocusPage === 'settings'
      ? document.querySelector<HTMLElement>('[data-tour="replay-tour"]') : null
    const destination = opener ?? document.querySelector<HTMLElement>(`[data-tour="nav-${pendingFocusPage}"]`)
    destination?.focus()
    setPendingFocusPage(null)
  }, [active, currentPage, pendingFocusPage])
  function dismiss() { endTour(); restoreFocus() }
  useEffect(() => {
    if (!active) { restoreFocus(); return }
    returnFocus.current = document.activeElement as HTMLElement | null
    returnPage.current = currentPageRef.current
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); endTour(); restoreFocus() }
      if (event.key === 'Tab') {
        const buttons = Array.from(calloutRef.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])
        const first = buttons[0], last = buttons.at(-1)
        if (!first || !last) return
        if (event.shiftKey && (document.activeElement === first || !buttons.includes(document.activeElement as HTMLButtonElement))) {
          event.preventDefault(); last.focus()
        } else if (!event.shiftKey && (document.activeElement === last || !buttons.includes(document.activeElement as HTMLButtonElement))) {
          event.preventDefault(); first.focus()
        }
      }
    }
    window.addEventListener('keydown', keydown, true)
    return () => { window.removeEventListener('keydown', keydown, true) }
  }, [active, restoreFocus])


  useEffect(() => {
    if (!active || !step) return
    if (step.page && step.page !== currentPage) {
      onNavigate(step.page)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, stepIndex])

  useEffect(() => {
    if (!active || !step) { setRect(null); return }
    let cancelled = false, raf = 0
    const target = step.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null
    let observedTarget = target
    const measure = () => {
      if (cancelled) return
      const el = step.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null
      if (el && el !== observedTarget) {
        observedTarget = el
        el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' })
        observer?.observe(el)
      }
      const next = el?.getBoundingClientRect() ?? null
      setRect(prev => prev?.left === next?.left && prev?.top === next?.top && prev?.width === next?.width && prev?.height === next?.height ? prev : next)
      setViewport(prev => prev.width === window.innerWidth && prev.height === window.innerHeight ? prev : { width: window.innerWidth, height: window.innerHeight })
      const panel = calloutRef.current?.getBoundingClientRect()
      if (panel) setSize(prev => prev.width === panel.width && prev.height === panel.height ? prev : { width: panel.width, height: panel.height })
    }
    const schedule = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(measure) }
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(schedule)
    if (target) { target.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' }); observer?.observe(target) }
    if (calloutRef.current) observer?.observe(calloutRef.current)
    const timer = setTimeout(() => {
      const late = step.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null
      late?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' })
      if (late && late !== target) observer?.observe(late)
      measure(); schedule()
      calloutRef.current?.querySelector<HTMLButtonElement>('button')?.focus()
    }, 80)
    measure()
    const mutations = typeof MutationObserver === 'undefined' ? null : new MutationObserver(schedule)
    mutations?.observe(document.documentElement, { childList: true, subtree: true })
    window.addEventListener('resize', schedule)
    window.addEventListener('scroll', schedule, true)
    return () => { cancelled = true; clearTimeout(timer); cancelAnimationFrame(raf); observer?.disconnect(); mutations?.disconnect(); window.removeEventListener('resize', schedule); window.removeEventListener('scroll', schedule, true) }
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
  const calloutStyle: React.CSSProperties = {
    position: 'fixed', ...computeTourCallout(rect, viewport, size), zIndex: 101,
    width: 'min(320px, calc(100vw - 32px))',
  }

  return (
    <AnimatePresence>
      <div aria-hidden="true" style={{ position: "fixed", inset: 0, zIndex: 99 }} />
      <motion.div
        key={stepIndex}
        style={spotlightStyle}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      />
      <motion.div
        key={`callout-${stepIndex}`}
        ref={calloutRef}
        role="dialog"
        aria-modal="true"
        aria-label="Product tour"
        style={calloutStyle}
        className="flex flex-col overflow-hidden rounded-lg border border-border bg-card p-4 shadow-2xl"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.2 }}
      >
        <div className="mb-2 flex shrink-0 items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Step {stepIndex + 1} / {totalSteps}
          </span>
          <button type="button" onClick={dismiss} className="text-xs text-muted-foreground hover:text-foreground">
            Skip
          </button>
        </div>
        <h3 className="mb-1 shrink-0 text-sm font-bold" style={{ fontFamily: "var(--font-display)" }}>
          {step.title}
        </h3>
        <p className="mb-4 min-h-0 overflow-y-auto text-xs text-muted-foreground">{step.description}</p>
        <div className="flex shrink-0 items-center justify-between">
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
