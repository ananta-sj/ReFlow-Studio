import { useEffect, useRef, useState } from "react"
import { Upload } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { CornerFrame } from "@/components/panels/CornerFrame"
import { RadialGauge } from "@/components/panels/RadialGauge"
import { cn } from "@/lib/utils"
import {
  bridge,
  type DeviceEtaMap,
  type DeviceInfo,
  type EngineReadiness,
  type Language,
  type ModelEntry,
  type PipelineTemplateId,
  type PipelineTemplateMap,
} from "@/lib/api"
import { useRenderJob } from "@/lib/use-render"
import { buildRenderParams } from "@/lib/render-params"
import { addToQueue, useQueue } from "@/lib/use-queue"
import { QUALITY_STEPS, updateConfig, useRenderConfig } from "@/lib/use-render-config"
import { levelAtLeast, type ExperienceLevel } from "@/lib/use-experience"
import { confirmAction } from "@/lib/use-confirm"
import { loadGaugeColor } from "@/lib/gauge-color"
import { formatDuration, relativeSpeedPercent, projectedLoadPercent, jobMemoryBudget } from "@/lib/eta"
import { HelpTooltip } from "@/components/shared/HelpTooltip"
import { SourceLanguageReport } from "@/components/shared/SourceLanguageReport"
import { CueReviewPanel } from "@/components/shared/CueReviewPanel"
import type { PageId } from "@/components/shell/PrimaryNav"

interface DashboardProps {
  selectedDeviceId: string
  level: ExperienceLevel
  onNavigate: (page: PageId) => void
}

export function Dashboard({ selectedDeviceId, level, onNavigate }: DashboardProps) {
  const isAdvanced = levelAtLeast(level, "advanced")
  const isExpert = levelAtLeast(level, "expert")
  const queue = useQueue()
  const videoPath = queue[0]?.input_path ?? null
  const cfg = useRenderConfig()
  const [voices, setVoices] = useState<ModelEntry[]>([])
  const [templates, setTemplates] = useState<PipelineTemplateMap | null>(null)
  const [inputPath, setInputPath] = useState<string | null>(null)
  const [devices, setDevices] = useState<DeviceInfo[]>([])
  const [deviceEtas, setDeviceEtas] = useState<DeviceEtaMap>({})
  const [selectedVram, setSelectedVram] = useState<{ used: number | null; total: number | null }>({
    used: null, total: null,
  })
  const [languages, setLanguages] = useState<Language[]>([])
  const [sourceLanguages, setSourceLanguages] = useState<Language[]>([])
  const [sourceLanguageError, setSourceLanguageError] = useState<string | null>(null)
  const [setupReport, setSetupReport] = useState<EngineReadiness | null>(null)
  const [checkingSetup, setCheckingSetup] = useState(false)
  const [setupError, setSetupError] = useState<string | null>(null)
  const setupRequest = useRef(0)

  const render = useRenderJob()

  useEffect(() => {
    bridge.listModels("voice").then((models) => setVoices(models.filter((m) => m.status === "installed")))
    bridge.listPipelineTemplates().then(setTemplates)
    bridge.getHardwareSnapshot().then((snap) => setDevices(snap.devices))
    bridge.listLanguages().then(setLanguages)
    bridge.listSourceLanguages().then(setSourceLanguages).catch(() => {
      setSourceLanguageError("Could not load source languages. Restart Reflow to try again.")
    })
  }, [])

  // Current VRAM headroom for whichever device is selected, so the
  // Projected System Load gauge reflects "what's already used" + "what
  // this job would add," not just the job's footprint in isolation.
  useEffect(() => {
    let cancelled = false
    setSelectedVram({ used: null, total: null })
    bridge.getHardwareSnapshot(selectedDeviceId).then((snap) => {
      if (!cancelled) setSelectedVram({ used: snap.vram_used_mb, total: snap.vram_total_mb })
    }).catch(() => {})
    return () => { cancelled = true }
  }, [selectedDeviceId])

  const inputKind = templates?.[cfg.template]?.input_kind ?? "video"
  const effectivePath = inputKind === "video" ? videoPath : inputPath

  // ETA only means something for an actual video render - stt/tts/lipsync/etc
  // stage costs don't apply to audio_dub or subtitle_translate the same way,
  // and _probe_duration() expects a media file, not a subtitle file.
  useEffect(() => {
    let cancelled = false
    setDeviceEtas({})
    if (inputKind !== "video" || !videoPath) {
      return
    }
    bridge
      .estimateJobAllDevices(videoPath, {
        ...buildRenderParams(cfg, selectedDeviceId, "video"),
      })
      .then((result) => { if (!cancelled) setDeviceEtas(result) })
      .catch(() => { if (!cancelled) setDeviceEtas({}) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputKind, videoPath, cfg.template, cfg.keepBg, cfg.lipsync, cfg.enhance, cfg.contentFilter, cfg.parallelWorkers, cfg.voice, cfg.lang, cfg.sourceLanguage, cfg.qualityIdx])

  async function handleBrowseVideo() {
    const files = await bridge.browseVideo()
    if (files.length > 0) await addToQueue(files)
  }

  async function handleBrowseAudio() {
    const file = await bridge.browseAudio()
    if (file) updateConfig({ refAudio: file })
  }

  async function handleBrowseSourceInput() {
    if (inputKind === "video") return handleBrowseVideo()
    const file = inputKind === "subtitle" ? await bridge.browseSubtitle() : await bridge.browseAudio()
    if (file) setInputPath(file)
  }

  const params = buildRenderParams(cfg, selectedDeviceId, inputKind)

  // Clear stale inspection results whenever the requested route changes.
  const setupKey = JSON.stringify({ params, template: cfg.template })
  useEffect(() => {
    setupRequest.current += 1
    setSetupReport(null)
    setSetupError(null)
  }, [setupKey])

  async function handleCheckSetup(verifyRuntime = false) {
    const request = ++setupRequest.current
    setCheckingSetup(true)
    setSetupError(null)
    setSetupReport(null)
    try {
      const report = await bridge.getEngineReadiness(params, cfg.template, verifyRuntime)
      if (setupRequest.current === request) setSetupReport(report)
    } catch {
      if (setupRequest.current === request) setSetupError("Could not inspect this setup. Try again before starting the job.")
    } finally { setCheckingSetup(false) }
  }

  const selectedEstimate = deviceEtas[selectedDeviceId]
  const deviceBudgets = selectedEstimate?.peak_vram_by_device_mb
  const selectedBudget = jobMemoryBudget(selectedEstimate, selectedDeviceId)
  const loadPercent = selectedBudget == null ? null : projectedLoadPercent(
    selectedVram.used, selectedVram.total, selectedBudget
  )
  const loadTooHigh = loadPercent != null && loadPercent >= 95

  async function handleStart() {
    if (!effectivePath) return

    if (loadTooHigh) {
      await confirmAction({
        title: "Projected load too high",
        description: `This job's projected VRAM usage is ${Math.round(loadPercent!)}% of "${devices.find((d) => d.id === selectedDeviceId)?.label ?? selectedDeviceId}"'s capacity - too close to the limit to safely start. Pick a different device, disable a heavier stage, or free up VRAM first.`,
        alertOnly: true,
      })
      return
    }

    const ok = await confirmAction({
      title: inputKind === "video" ? "Start video batch?" : "Initialize pipeline?",
      description: inputKind === "video" ? `Starts ${queue.length} pending video jobs in order. New jobs use ${templates?.[cfg.template]?.label ?? 'video dubbing'}, ${devices.find((device) => device.id === selectedDeviceId)?.label ?? selectedDeviceId}, ${languages.find((language) => language.code === cfg.lang)?.name ?? cfg.lang}, and the current stage settings. Previously accepted jobs retain their settings.` : `Starts rendering "${effectivePath.split(/[\\/]/).pop()}" now. This uses the currently selected device and stage settings.`,
      confirmLabel: inputKind === "video" ? "Start Batch" : "Initialize Pipeline",
    })
    if (!ok) return
    const result = inputKind === "video" ? await render.startBatch(params, cfg.template, queue.map((job) => job.id)) : await render.start(effectivePath, params, cfg.template)
    if (!result.ok) await confirmAction({ title: "Start unavailable", description: result.message ?? "The job was not accepted.", alertOnly: true })
    else if (inputKind !== "video") setInputPath(null)
  }

  const priorityMode = cfg.taskPriority < 25 ? "MAX SPEED" : cfg.taskPriority < 75 ? "BALANCED" : "MAX QUALITY"

  return (
    <div className="flex flex-col gap-4 p-6">
      {/* Row 1: everything that fits comfortably side by side, instead of
          stacking full-width cards and forcing a long vertical scroll -
          the window is wide, so use the width. */}
      <div
        className={cn(
          "grid grid-cols-1 gap-4",
          isAdvanced ? "xl:grid-cols-3" : "xl:grid-cols-2"
        )}
      >
        <CornerFrame>
          <Card className="h-full border-border bg-card" data-tour="dashboard-source">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Upload className="h-4 w-4 text-primary" /> 01 // SOURCE INPUT
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {render.isRunning && (
                <div className="rounded-md border border-primary/30 bg-primary/5 p-3" role="status">
                  <p className="text-xs font-medium">{render.isStopping ? "Stopping render" : "Currently rendering"}</p>
                  <p className="mt-1 break-all text-sm" title={render.inputPath ?? undefined}>
                    {render.inputPath?.split(/[\\/]/).pop() ?? "Waiting for active input details"}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Selections and settings below apply to future jobs. Accepted batch jobs retain their saved settings.
                  </p>
                </div>
              )}
              {templates && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs text-muted-foreground">Pipeline Template</span>
                  <Select
                    value={cfg.template}
                    onValueChange={(v) => {
                      updateConfig({ template: v as PipelineTemplateId,
                        lipsync: v === "video_dub_lipsync" ? true : cfg.template === "video_dub_lipsync" ? false : cfg.lipsync })
                      setInputPath(null)
                    }}
                  >
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(templates).map(([id, t]) => (
                        <SelectItem key={id} value={id}>{t.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                {render.isRunning
                  ? inputKind === "video" ? "Next pending video" : "Selected input for a future job"
                  : "Selected input"}
              </p>
              <button
                type="button"
                onClick={handleBrowseSourceInput}
                className="flex w-full flex-col items-center gap-3 rounded-lg border-2 border-dashed border-border bg-muted/20 py-8 text-center hover:border-primary/50"
              >
                <Upload className="h-7 w-7 text-muted-foreground" />
                <div className="text-sm font-medium">
                  {effectivePath
                    ? effectivePath.split(/[\\/]/).pop()
                    : `Click to select ${inputKind} file${inputKind === "video" ? "(s)" : ""}`}
                </div>
                <div className="text-xs text-muted-foreground">
                  {inputKind === "video" && `MP4, MOV, AVI, MKV${queue.length > 1 ? ` · ${queue.length} queued` : ""}`}
                  {inputKind === "audio" && "WAV, MP3"}
                  {inputKind === "subtitle" && "SRT"}
                </div>
              </button>
            </CardContent>
          </Card>
        </CornerFrame>

        <Card className="h-full border-border bg-card">
          <CardHeader>
            <CardTitle className="text-sm">02 // PROCESSING PIPELINE</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button variant="outline" onClick={() => handleCheckSetup()} disabled={checkingSetup || render.isRunning}>
              {checkingSetup ? "Checking setup…" : "Check selected setup"}
            </Button>
            <Button variant="outline" onClick={() => handleCheckSetup(true)} disabled={checkingSetup || render.isRunning}>
              Check runtime dependencies and device
            </Button>
            <p className="text-[11px] text-muted-foreground">Checks local files and selected routes. No downloads or provider calls.</p>
            <p className="text-[11px] text-muted-foreground">Runtime checks import installed dependencies and test a small calculation. Checks have a 45–90 second limit per engine, depending on its import chain. Models are not loaded.</p>
            {setupError && <p role="alert" className="text-xs text-destructive">{setupError}</p>}
            {setupReport && <div className="space-y-2 text-xs" aria-live="polite">
              <p>{setupReport.explanation}</p>
              {setupReport.warnings.map((warning) => <p key={warning}>{warning}</p>)}
              {setupReport.checks.map((check, index) => <div key={`${check.stage}-${index}`} className="rounded border border-border p-2">
                <p className={check.status === "needs_setup" ? "text-destructive" : "font-medium"}>
                  {check.label}{check.model ? ` · ${check.model}` : ""} — {check.status === "needs_setup" ? "Needs setup" : check.status === "checked" ? "Files checked" : "Not verified"}
                </p>
                {check.details.map((detail) => <p key={detail} className="mt-1 text-muted-foreground">{detail}</p>)}
                {check.runtime && <p className="mt-1">Runtime: {check.runtime.status === "passed" ? "dependencies and device checked" : check.runtime.status === "failed" ? "needs attention" : "not checked"}{check.runtime.device_name ? ` · ${check.runtime.device_name}` : ""}</p>}
                {check.guidance && <p className="mt-1">{check.guidance}</p>}
              </div>)}
            </div>}
            <div className="flex flex-col gap-1.5">
              <span id="source-language-label" className="text-xs text-muted-foreground">Source Language</span>
              <Select value={cfg.sourceLanguage} onValueChange={(v) => updateConfig({ sourceLanguage: v })}
                disabled={render.isRunning || sourceLanguageError !== null}>
                <SelectTrigger className="w-full" aria-labelledby="source-language-label"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto</SelectItem>
                  {sourceLanguages.map(({ code, name }) => (
                    <SelectItem key={code} value={code}>{name} ({code})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[11px] text-muted-foreground">
                {inputKind === "subtitle"
                  ? "Subtitle files have no audio detection. Choose a source for M2M100 or NLLB; prompt-based translators can infer it."
                  : "Auto uses transcription detection. M2M100 and NLLB require at least 80% confidence; otherwise choose the source manually."}
              </p>
              {cfg.sourceLanguage !== "auto" && <p className="text-[11px] text-muted-foreground">
                This source is remembered for future jobs. It overrides translation, not transcription. Check it when changing files.
              </p>}
              {sourceLanguageError && <p role="alert" className="text-xs text-destructive">{sourceLanguageError}</p>}
            </div>
            <div className="flex flex-col gap-1.5">
              <span id="target-language-label" className="text-xs text-muted-foreground">
                Target Language
              </span>
              <Select value={cfg.lang} onValueChange={(v) => updateConfig({ lang: v })}>
                <SelectTrigger className="w-full" aria-labelledby="target-language-label"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {languages.map(({ code, name }) => (
                    <SelectItem key={code} value={code}>{name} ({code})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {inputKind !== "subtitle" && (
              <>
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Voice Model</span>
                    <button
                      type="button"
                      onClick={() => onNavigate("marketplace")}
                      className="text-[11px] text-primary hover:underline"
                    >
                      Manage in Marketplace →
                    </button>
                  </div>
                  <Select value={cfg.voice} onValueChange={(v) => updateConfig({ voice: v })}>
                    <SelectTrigger className="w-full" aria-label="Voice Model"><SelectValue placeholder="Selected voice unavailable — choose a voice" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="CLONED_USER">Use selected speech engine / reference audio</SelectItem>
                      {voices.map((v) => (
                        <SelectItem key={v.id} value={v.id}>{v.display_name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button variant="outline" size="sm" onClick={handleBrowseAudio}>
                  {cfg.refAudio ? cfg.refAudio.split(/[\\/]/).pop() : "Select Reference Audio"}
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {isAdvanced && inputKind !== "subtitle" && (
          <Card className="h-full border-border bg-card">
            <CardHeader>
              <CardTitle className="text-sm">03 // CONFIGURATION</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {(
                [
                  ["Preserve Background", cfg.keepBg, (v: boolean) => updateConfig({ keepBg: v }), true,
                    "Separates and keeps the original background music/ambience, mixing the new dubbed voice on top instead of replacing the whole audio track."],
                  ["Lip Sync Engine", cfg.template === "video_dub_lipsync" || cfg.lipsync,
                    (v: boolean) => updateConfig({ lipsync: v,
                      ...(cfg.template === "video_dub_lipsync" && !v ? { template: "video_dub" as PipelineTemplateId } : {}) }), inputKind === "video",
                    "Reshapes the speaker's mouth movement in the video to match the new dubbed audio."],
                  ["Face Enhancer", cfg.enhance, (v: boolean) => updateConfig({ enhance: v }), inputKind === "video",
                    "Runs the active Enhancer model over every frame to sharpen/upscale faces. Slower, and the Texture Quality slider below controls its strength."],
                  ["Include Subtitles", cfg.includeSubtitles, (v: boolean) => updateConfig({ includeSubtitles: v }), inputKind === "video",
                    "Includes translated subtitles in the finished video. Turn this off for a video without subtitles."],
                  ["Export Audio Stems", cfg.exportStems, (v: boolean) => updateConfig({ exportStems: v }), true,
                    "Saves source vocals, available background, dubbed speech and the final mix together with the completed render."],
                  ["Burn-in Subtitles", cfg.burnSubs, (v: boolean) => updateConfig({ burnSubs: v }), inputKind === "video" && cfg.includeSubtitles,
                    "Permanently draws the translated subtitles onto the video frames, instead of leaving them as a separate, toggleable subtitle track."],
                  ["Content Filter", cfg.contentFilter, (v: boolean) => updateConfig({ contentFilter: v }), inputKind === "video",
                    "Runs the active Visual Filter model over every frame to detect and blur unsafe content before the final render is saved."],
                ] as [string, boolean, (v: boolean) => void, boolean, string][]
              )
                .filter(([, , , visible]) => visible)
                .map(([label, value, setter, , help]) => (
                  <div key={label} className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm">{label}</span>
                      <HelpTooltip text={help} />
                    </div>
                    <Switch checked={value} onCheckedChange={setter} />
                  </div>
                ))}
              {inputKind === "video" && cfg.includeSubtitles && cfg.burnSubs && (
                <label className="flex items-center justify-between text-sm">
                  Subtitle size
                  <Select value={String(cfg.subtitleFontSize)} onValueChange={(value) => updateConfig({ subtitleFontSize: Number(value) })}>
                    <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                    <SelectContent>{[18, 24, 32, 40].map((size) => <SelectItem key={size} value={String(size)}>{size}</SelectItem>)}</SelectContent>
                  </Select>
                </label>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Row 2: priority/quality + ETA + (Expert) the exact render params
          preview, side by side rather than each eating a full-width row. */}
      {isAdvanced && (
        <div className={cn("grid grid-cols-1 gap-4", isExpert ? "xl:grid-cols-3" : "xl:grid-cols-2")}>
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-sm">04 // TASK PRIORITY &amp; QUALITY</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div className="flex flex-col gap-2">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span>Task Priority (speed ↔ quality)</span>
                    <HelpTooltip text="Picks the ffmpeg encode preset. Lower favors a faster render; higher favors output quality." />
                  </div>
                  <span className="text-primary">{cfg.taskPriority} · {priorityMode}</span>
                </div>
                <Slider
                  value={[cfg.taskPriority]}
                  onValueChange={([v]) => updateConfig({ taskPriority: v })}
                  max={100}
                  step={1}
                />
              </div>
              <div className="flex flex-col gap-2">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span>Texture Quality (Face Enhancer upscale)</span>
                    <HelpTooltip text="Upscale factor applied by the Face Enhancer stage when it's enabled. Higher looks better but takes longer and uses more VRAM." />
                  </div>
                  <span className="text-primary">{QUALITY_STEPS[cfg.qualityIdx]}x</span>
                </div>
                <Slider
                  value={[cfg.qualityIdx]}
                  onValueChange={([v]) => updateConfig({ qualityIdx: v })}
                  max={QUALITY_STEPS.length - 1}
                  step={1}
                />
              </div>
            </CardContent>
          </Card>

          {inputKind === "video" && (
            <Card className="border-border bg-card" data-tour="dashboard-estimate">
              <CardHeader>
                <CardTitle className="text-sm">05 // RENDER ESTIMATE</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center gap-3">
                {videoPath && <p className="w-full break-all text-center text-xs text-muted-foreground">
                  Estimate for selected input: {videoPath.split(/[\\/]/).pop()}. Uses the selected settings.
                </p>}
                {!videoPath ? (
                  <p className="py-4 text-center text-xs text-muted-foreground">
                    Select a video to see an estimate.
                  </p>
                ) : (
                  <>
                    <div className="flex w-full items-center justify-around">
                      <RadialGauge
                        percent={relativeSpeedPercent(deviceEtas, selectedDeviceId)}
                        label="EST. TIME"
                        sublabel={devices.find((d) => d.id === selectedDeviceId)?.label ?? selectedDeviceId}
                        color="var(--secondary)"
                        centerLabel={formatDuration(deviceEtas[selectedDeviceId]?.eta_seconds)}
                        size={92}
                      />
                      {loadPercent == null ? (
                        <div className="flex w-[92px] flex-col items-center gap-1 text-center">
                          <div className="flex h-[92px] w-[92px] items-center justify-center rounded-full border border-dashed border-border p-2">
                            <span className="text-[10px] leading-tight text-muted-foreground">
                              {selectedVram.total == null || selectedVram.used == null ? "VRAM unreadable for this device" : "GPU memory estimate unavailable"}
                            </span>
                          </div>
                          <span className="text-xs font-medium text-muted-foreground">PROJECTED LOAD</span>
                        </div>
                      ) : (
                        <div className="relative">
                          <RadialGauge
                            percent={loadPercent}
                            label="PROJECTED LOAD"
                            sublabel={`${Math.round((selectedVram.used ?? 0) + (selectedBudget ?? 0))} / ${selectedVram.total} MB`}
                            color={loadGaugeColor(loadPercent)}
                            size={92}
                          />
                          {loadTooHigh && (
                            <div className="pointer-events-none absolute inset-0 top-0 flex h-[92px] w-[92px] flex-col items-center justify-center rounded-full bg-destructive/85 text-center">
                              <span className="text-[9px] font-bold leading-tight text-white">
                                NOT
                                <br />
                                RECOMMENDED
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex w-full flex-col gap-1">
                      {devices.map((d) => (
                        <div key={d.id} className="flex items-center justify-between text-[11px]">
                          <span className={cn("truncate", d.id === selectedDeviceId && "text-primary")}>
                            {d.label}
                          </span>
                          <span className="text-muted-foreground">
                            {formatDuration(deviceEtas[d.id]?.eta_seconds)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="text-center text-[10px] text-muted-foreground/70">
                      Uncalibrated estimates. GPU budgets add model estimates across stages. Downloads and service latency are excluded.
                      {deviceEtas[selectedDeviceId]?.audio_buffer_ram_mb != null &&
                        ` Audio buffers: about ${Math.round(deviceEtas[selectedDeviceId].audio_buffer_ram_mb!)} MB RAM, plus model memory.`}
                    </p>
                    {Object.entries(deviceBudgets ?? {}).map(([device, budget]) => (
                      <p key={device} className="text-center text-[11px] text-muted-foreground">
                        {devices.find((item) => item.id === device)?.label ?? device}: {budget == null ? "GPU memory estimate unavailable" : `about ${Math.round(budget)} MB additional memory budget`}
                      </p>
                    ))}
                    {deviceEtas[selectedDeviceId]?.warnings?.map((warning) => (
                      <p key={warning} className="text-center text-[11px] text-amber-500">{warning}</p>
                    ))}
                  </>
                )}
              </CardContent>
            </Card>
          )}

          {isExpert && (
            <Card className="border-border bg-card">
              <CardHeader>
                <CardTitle className="text-sm">06 // RENDER PARAMS (EXPERT)</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="mb-2 text-[11px] text-muted-foreground">
                  Selected settings for new jobs. Accepted batch jobs retain their saved settings.
                </p>
                <pre
                  className="max-h-40 overflow-auto rounded-md border border-border bg-muted/30 p-3 text-[11px] text-muted-foreground"
                  style={{ fontFamily: "var(--font-mono)" }}
                >
                  {JSON.stringify(params, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {!isAdvanced && (
        <p className="text-center text-xs text-muted-foreground">
          Basic mode uses sensible defaults (background preserved, balanced
          speed/quality). Switch to ADVANCED for lip sync, face enhancement,
          subtitles, and fine-grained control.
        </p>
      )}

      {(inputKind === 'audio' || (inputKind === 'video' && cfg.template === 'video_dub')) && (
        <CueReviewPanel inputPath={effectivePath} params={params} />
      )}

      {render.status !== "idle" && (
        <Card className="border-border bg-card">
          <CardContent className="flex flex-col gap-2 pt-6">
            {render.inputPath && <p className="text-xs text-muted-foreground">
              {render.isRunning ? "Active input" : "Last render input"}: {render.inputPath.split(/[\\/]/).pop()}
            </p>}
            {render.sourceFeedback && (
              <SourceLanguageReport feedback={render.sourceFeedback} />
            )}
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">{render.statusText || render.status.toUpperCase()}</span>
              <span className="text-primary">{render.percent}%</span>
            </div>
            <Progress value={render.percent} />
            {render.stillWorking && (
              <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-warning" />
                Still working - this stage can take a while depending on your hardware.
              </div>
            )}
            {render.errorMessage && <div className="text-xs text-destructive">{render.errorMessage}</div>}
          </CardContent>
        </Card>
      )}

      {render.isRunning ? (
        <Button
          size="lg"
          variant="destructive"
          className="h-14 text-base font-bold tracking-widest [clip-path:polygon(0_0,100%_0,100%_calc(100%-14px),calc(100%-14px)_100%,0_100%)]"
          disabled={render.isStopping} onClick={() => render.stop()}
        >
          STOP RENDER
        </Button>
      ) : (
        <Button
          size="lg"
          data-tour="initialize-pipeline"
          className={cn(
            "h-14 text-base font-bold tracking-widest [clip-path:polygon(0_0,100%_0,100%_calc(100%-14px),calc(100%-14px)_100%,0_100%)]",
            loadTooHigh
              ? "bg-destructive text-white shadow-[0_0_24px_-4px_var(--destructive)] hover:bg-destructive/90"
              : "shadow-[0_0_24px_-4px_var(--primary)]"
          )}
          disabled={!effectivePath}
          onClick={handleStart}
        >
          {loadTooHigh ? "LOAD TOO HIGH - NOT RECOMMENDED" : inputKind === "video" ? "START VIDEO BATCH" : "INITIALIZE PIPELINE"}
        </Button>
      )}
    </div>
  )
}
