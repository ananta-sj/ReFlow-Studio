// First-run setup wizard - shown once (gated by settings.onboarding_complete,
// see App.tsx) the way a professional installer walks a user through
// experience level, starting defaults, and optional model downloads before
// dropping them into the app proper. Every choice here is also editable
// later from Settings/Marketplace - this is a convenience on-ramp, not the
// only place any of it lives.
import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { bridge, type AppSettings, type Language, type RecommendedModel, type StageType } from "@/lib/api"
import { useExperienceLevel, type ExperienceLevel } from "@/lib/use-experience"
import { cn } from "@/lib/utils"

const LEVEL_CHOICES: { id: ExperienceLevel; label: string; desc: string }[] = [
  { id: "basic", label: "Basic", desc: "One-click dubbing with sensible defaults. Pipeline internals stay out of the way." },
  { id: "advanced", label: "Advanced", desc: "Adds the Nodes graph and per-stage pipeline controls." },
  { id: "expert", label: "Expert", desc: "Adds raw settings, engine hosts, and credential-backed integrations." },
]

const STAGE_LABELS: Record<StageType, string> = {
  stt: "Speech-to-Text", translation: "Translation", tts: "Text-to-Speech", voice: "Voice Cloning",
  enhancer: "Video Enhancer", filter: "Visual Filter", lipsync: "Lipsync", profanity_filter: "Profanity Filter",
}

const STEP_LABELS = ["Welcome", "Defaults", "AirLLM", "Recommended Models", "Done"]

interface SetupWizardProps {
  onDone: () => void
}

export function SetupWizard({ onDone }: SetupWizardProps) {
  const [step, setStep] = useState(0)
  const { level, setLevel } = useExperienceLevel()
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [recommended, setRecommended] = useState<Partial<Record<StageType, RecommendedModel[]>>>({})
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [finishing, setFinishing] = useState(false)
  const [languages, setLanguages] = useState<Language[]>([])
  const [airllmEnabled, setAirllmEnabled] = useState(false)
  const [airllmName, setAirllmName] = useState("")
  const [airllmModelId, setAirllmModelId] = useState("")
  const [airllmCompression, setAirllmCompression] = useState("4bit")

  useEffect(() => {
    bridge.getSettings().then((res) => setSettings(res.values))
    bridge.listLanguages().then(setLanguages)
    Promise.all(
      (Object.keys(STAGE_LABELS) as StageType[]).map(async (stage) => {
        const models = await bridge.listRecommendedModels(stage)
        return [stage, models.filter((m) => m.kind === "local_file")] as const
      })
    ).then((pairs) => {
      const map: Partial<Record<StageType, RecommendedModel[]>> = {}
      for (const [stage, models] of pairs) {
        if (models.length) map[stage] = models
      }
      setRecommended(map)
    })
  }, [])

  function patchSetting(partial: Partial<AppSettings>) {
    setSettings((prev) => (prev ? { ...prev, ...partial } : prev))
  }

  function togglePick(key: string) {
    setPicked((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  async function finish() {
    setFinishing(true)
    await bridge.updateSettings({ ...(settings ?? {}), onboarding_complete: true })

    // Only ever registered + activated if the user explicitly opted in on
    // this step - AirLLM is never a silent default (see Marketplace's own
    // AirLLM tab and DEVELOPMENT_HISTORY.md's "Opt-In AirLLM" section for
    // why that matters).
    if (airllmEnabled && airllmName.trim() && airllmModelId.trim()) {
      const result = await bridge.addAirllmModel(airllmName.trim(), airllmModelId.trim(), airllmCompression)
      if (result.ok && result.model) {
        await bridge.setActiveModel("translation", result.model.id)
      }
    }

    const downloads: Promise<unknown>[] = []
    for (const [stage, models] of Object.entries(recommended) as [StageType, RecommendedModel[]][]) {
      for (const m of models) {
        if (picked[`${stage}::${m.name}`] && m.source_url) {
          downloads.push(bridge.addLocalModel(stage, m.source_url, m.name))
        }
      }
    }
    await Promise.all(downloads)
    setFinishing(false)
    onDone()
  }

  async function skipAll() {
    await bridge.updateSettings({ onboarding_complete: true })
    onDone()
  }

  const pickedCount = Object.values(picked).filter(Boolean).length

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-40 flex items-center justify-center bg-background/95 p-6 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Card className="flex max-h-[85vh] w-full max-w-2xl flex-col border-border bg-card">
          <CardContent className="flex flex-1 flex-col gap-5 overflow-y-auto pt-6">
            <div className="flex items-center justify-between">
              <h1 className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>
                WELCOME TO REFLOW STUDIO
              </h1>
              <span className="text-xs text-muted-foreground">
                Step {step + 1} / {STEP_LABELS.length}
              </span>
            </div>

            <div className="flex gap-1.5">
              {STEP_LABELS.map((label, i) => (
                <div key={label} className={cn("h-1 flex-1 rounded-full", i <= step ? "bg-primary" : "bg-muted")} />
              ))}
            </div>

            {step === 0 && (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">
                  Pick how much of the pipeline you want to see day to day. Change this anytime
                  from the top bar.
                </p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {LEVEL_CHOICES.map((choice) => (
                    <button
                      key={choice.id}
                      type="button"
                      onClick={() => setLevel(choice.id)}
                      className={cn(
                        "flex flex-col gap-1.5 rounded-md border p-3 text-left transition-colors",
                        level === choice.id ? "border-primary bg-primary/10" : "border-border hover:border-primary/40"
                      )}
                    >
                      <span className="text-sm font-semibold">{choice.label}</span>
                      <span className="text-[11px] text-muted-foreground">{choice.desc}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {step === 1 && settings && (
              <div className="flex flex-col gap-4">
                <p className="text-sm text-muted-foreground">
                  Starting defaults - every one of these can be changed later in Settings.
                </p>
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs text-muted-foreground">Default Language</span>
                  <Select value={settings.default_language} onValueChange={(v) => patchSetting({ default_language: v })}>
                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {languages.map(({ code, name }) => (
                        <SelectItem key={code} value={code}>{name} ({code})</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Preserve background audio by default</span>
                  <Switch checked={settings.keep_bg_default} onCheckedChange={(v) => patchSetting({ keep_bg_default: v })} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Visual content filter by default</span>
                  <Switch
                    checked={settings.content_filter_default}
                    onCheckedChange={(v) => patchSetting({ content_filter_default: v })}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm">Auto-clean temp files</div>
                    <div className="text-[11px] text-muted-foreground">Sweeps temp/ after each render.</div>
                  </div>
                  <Switch
                    checked={settings.auto_cleanup_temp}
                    onCheckedChange={(v) => patchSetting({ auto_cleanup_temp: v })}
                  />
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-col gap-4">
                <div className="flex items-start justify-between gap-3 rounded-md border border-border p-3">
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium">Enable AirLLM for Translation</span>
                    <p className="text-[11px] text-muted-foreground">
                      Runs a full Hugging Face model with layer-by-layer disk offloading -
                      much slower than the default translator, but works on hardware too
                      small to load the model normally. Optional; leave this off to use the
                      default translator, and you can always add it later from the
                      Marketplace instead.
                    </p>
                  </div>
                  <Switch checked={airllmEnabled} onCheckedChange={setAirllmEnabled} />
                </div>
                {airllmEnabled && (
                  <div className="flex flex-col gap-3 rounded-md border border-dashed border-border p-3">
                    <Input
                      placeholder="Display name"
                      value={airllmName}
                      onChange={(e) => setAirllmName(e.target.value)}
                    />
                    <Input
                      placeholder="Hugging Face model id (e.g. meta-llama/Meta-Llama-3-8B)"
                      value={airllmModelId}
                      onChange={(e) => setAirllmModelId(e.target.value)}
                    />
                    <Select value={airllmCompression} onValueChange={setAirllmCompression}>
                      <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="4bit">4-bit compression (lowest VRAM)</SelectItem>
                        <SelectItem value="8bit">8-bit compression</SelectItem>
                        <SelectItem value="">No compression (full precision)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[11px] text-muted-foreground">
                      Setting this active for Translation now means AirLLM is used from your
                      very first render - you can switch back to the default translator
                      anytime in the Marketplace.
                    </p>
                  </div>
                )}
              </div>
            )}

            {step === 3 && (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">
                  Optional - queue up any recommended models to download now. Everything here is
                  also available anytime from the Marketplace, and nothing installs unless you
                  check it.
                </p>
                {Object.keys(recommended).length === 0 ? (
                  <p className="text-xs text-muted-foreground">Loading recommendations…</p>
                ) : (
                  <div className="flex max-h-72 flex-col gap-4 overflow-y-auto pr-1">
                    {(Object.entries(recommended) as [StageType, RecommendedModel[]][]).map(([stage, models]) => (
                      <div key={stage} className="flex flex-col gap-1.5">
                        <span className="text-xs font-semibold text-muted-foreground">{STAGE_LABELS[stage]}</span>
                        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                          {models.map((m) => {
                            const key = `${stage}::${m.name}`
                            return (
                              <label
                                key={key}
                                className={cn(
                                  "flex cursor-pointer items-start gap-2 rounded-md border p-2 text-xs",
                                  picked[key] ? "border-primary bg-primary/10" : "border-border"
                                )}
                              >
                                <input
                                  type="checkbox"
                                  className="mt-0.5"
                                  checked={!!picked[key]}
                                  onChange={() => togglePick(key)}
                                />
                                <span className="flex flex-col gap-0.5">
                                  <span className="flex items-center gap-1.5">
                                    <span className="font-medium">{m.name}</span>
                                    {m.best_for_device && (
                                      <span className="rounded bg-primary/15 px-1 py-0.5 text-[9px] font-medium text-primary">
                                        Best For This Device
                                      </span>
                                    )}
                                  </span>
                                  <span className="text-[10px] text-muted-foreground">{m.note}</span>
                                </span>
                              </label>
                            )
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {step === 4 && (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <span className="text-sm">
                  {finishing
                    ? pickedCount > 0
                      ? `Starting ${pickedCount} download${pickedCount === 1 ? "" : "s"}…`
                      : "Finishing up…"
                    : "All set. Revisit any of this in Settings or the Marketplace anytime."}
                </span>
              </div>
            )}
          </CardContent>

          <div className="flex items-center justify-between border-t border-border p-4">
            <Button variant="ghost" size="sm" onClick={skipAll} disabled={finishing}>
              Skip setup
            </Button>
            <div className="flex items-center gap-2">
              {step > 0 && (
                <Button variant="outline" size="sm" onClick={() => setStep((s) => s - 1)} disabled={finishing}>
                  Back
                </Button>
              )}
              {step < STEP_LABELS.length - 1 ? (
                <Button size="sm" onClick={() => setStep((s) => s + 1)}>Next</Button>
              ) : (
                <Button size="sm" onClick={finish} disabled={finishing}>
                  {finishing ? "Finishing…" : "Finish"}
                </Button>
              )}
            </div>
          </div>
        </Card>
      </motion.div>
    </AnimatePresence>
  )
}
