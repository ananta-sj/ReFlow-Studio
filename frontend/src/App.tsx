import { useEffect, useState } from "react"
import "./lib/events"
import { TitleBar } from "@/components/shell/TitleBar"
import { PrimaryNav, type PageId } from "@/components/shell/PrimaryNav"
import { IconRail } from "@/components/shell/IconRail"
import { BootScreen } from "@/components/shell/BootScreen"
import { SetupWizard } from "@/components/onboarding/SetupWizard"
import { ProductTour } from "@/components/onboarding/ProductTour"
import { ConfirmDialogHost } from "@/lib/use-confirm"
import { hasTourCompleted, startTour } from "@/lib/use-tour"
import { HardwareIntelligence } from "@/components/panels/HardwareIntelligence"
import { LogConsole } from "@/components/panels/LogConsole"
import { Dashboard } from "@/pages/Dashboard"
import { NodesPage } from "@/pages/Nodes"
import { AssetsPage } from "@/pages/Assets"
import { MarketplacePage } from "@/pages/Marketplace"
import { LogsPage } from "@/pages/Logs"
import { SettingsPage } from "@/pages/Settings"
import { bridge } from "@/lib/api"
import { confirmAction, confirmChoice } from "@/lib/use-confirm"
import { useTheme } from "@/lib/use-theme"
import { useAccentColor } from "@/lib/use-accent-color"
import { initializeJobs, runJobAction } from "@/lib/use-jobs"
import { useExperienceLevel, levelAtLeast } from "@/lib/use-experience"

const MIN_BOOT_MS = 1400

function App() {
  const [page, setPage] = useState<PageId>("dashboard")
  const [online, setOnline] = useState(false)
  const [selectedDeviceId, setSelectedDeviceId] = useState("cpu")
  const [booting, setBooting] = useState(true)
  const [bootStatus, setBootStatus] = useState("CONNECTING TO PYTHON CORE…")
  const [showWizard, setShowWizard] = useState(false)
  const { theme, toggle: toggleTheme } = useTheme()
  const { level, setLevel } = useExperienceLevel()
  useAccentColor() // applies the saved accent color to :root on mount

  useEffect(() => {
    initializeJobs()
    const bootStart = Date.now()

    bridge.runIntegrityCheck().then((result) => {
      setOnline(result.ok)
      setBootStatus(result.ok ? "SYSTEMS ONLINE" : "RUNTIME NEEDS ATTENTION")
      window.__reflow.dispatch("log", {
        level: result.ok ? "success" : "warning",
        message: result.message,
      })

      bridge.getSettings().then((res) => {
        if (!res.values.onboarding_complete) setShowWizard(true)
      })

      // Captures once (a no-op on every later boot - see
      // capture_hardware_profile()) so the Marketplace's "Best For This
      // Device" hint on recommended models has something to compare
      // against from the very first time it's shown.
      bridge.captureHardwareProfile()

      // A non-null result means the app didn't shut down cleanly last time
      // during a render (crash, force-kill, power loss) - a normal finish,
      // Stop, or render error always clears this marker (see
      // core/render_state.py). Restart may reuse verified recognition and
      // translation checkpoints; other stages run again with the same params.
      bridge.getInterruptedRender().then((interrupted) => {
        if (!interrupted) return
        confirmChoice({
          title: "Resume interrupted render?",
          description: `Reflow Studio closed unexpectedly while rendering "${interrupted.input_path.split(/[\\/]/).pop()}". Restart this render? Verified recognition and translation checkpoints may be reused; other stages run again. Other restored batch jobs stay paused. Closing this dialog keeps the recovery record for the next launch.`,
          confirmLabel: "Resume Render",
          cancelLabel: "Discard",
        }).then(async (choice) => {
          if (choice === 'confirm') {
            const result = await runJobAction(() => bridge.resumeInterruptedRender(interrupted.recovery_token))
            if (!result.ok) await confirmAction({ title: "Resume unavailable", description: result.message ?? "The restart was not accepted.", alertOnly: true })
          } else if (choice === 'cancel') {
            try {
              const result = await bridge.discardInterruptedRender(interrupted.recovery_token)
              if (!result.ok) await confirmAction({ title: "Discard unavailable", description: result.message ?? "The recovery record could not be removed.", alertOnly: true })
            } catch (error) {
              await confirmAction({ title: "Discard unavailable", description: String(error), alertOnly: true })
            }
          }
        })
      })

      const elapsed = Date.now() - bootStart
      setTimeout(() => setBooting(false), Math.max(0, MIN_BOOT_MS - elapsed))
    })
  }, [])

  // The Nodes tab only exists at Advanced+ - if the user drops back to
  // Basic while on it, don't strand them on a page its own nav no longer
  // shows a tab for.
  useEffect(() => {
    if (page === "nodes" && !levelAtLeast(level, "advanced")) {
      setPage("dashboard")
    }
  }, [page, level])

  return (
    <>
      <BootScreen visible={booting} statusText={bootStatus} />
      <ConfirmDialogHost />
      {!booting && showWizard && (
        <SetupWizard
          onDone={() => {
            setShowWizard(false)
            // Auto-runs once, right after first-run setup - see
            // lib/use-tour.ts. Replayable anytime from Settings
            // ("Replay Tour"), which calls startTour() directly and
            // doesn't go through this completed-check.
            if (!hasTourCompleted()) startTour()
          }}
        />
      )}
      <ProductTour currentPage={page} onNavigate={setPage} />
      <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
        <TitleBar onNavigate={setPage} theme={theme} onToggleTheme={toggleTheme} />
        <PrimaryNav
          activePage={page}
          onNavigate={setPage}
          level={level}
          onLevelChange={setLevel}
          online={online}
        />

        <div className="flex flex-1 overflow-hidden">
          <IconRail activePage={page} onNavigate={setPage} level={level} />

          <main className="flex-1 overflow-y-auto">
            {page === "dashboard" && (
              <Dashboard selectedDeviceId={selectedDeviceId} level={level} onNavigate={setPage} />
            )}
            {page === "nodes" && levelAtLeast(level, "advanced") && <NodesPage />}
            {page === "assets" && <AssetsPage onNavigate={setPage} />}
            {page === "marketplace" && <MarketplacePage />}
            {page === "logs" && <LogsPage />}
            {page === "settings" && <SettingsPage level={level} />}
          </main>

          {page !== "logs" && (
            <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto border-l border-border p-3">
              <HardwareIntelligence onDeviceSelected={setSelectedDeviceId} />
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold tracking-wide text-muted-foreground">
                  08 // SYSTEM LOG
                </span>
                {/* Fixed height, not min-height - a min-height fighting a
                    flex-1 parent is what caused the sidebar's content to
                    silently overflow its container instead of either
                    fitting cleanly or scrolling predictably. */}
                <LogConsole className="h-[220px] text-[10px]" />
              </div>
            </aside>
          )}
        </div>
      </div>
    </>
  )
}

export default App
