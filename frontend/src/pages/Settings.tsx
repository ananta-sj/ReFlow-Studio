import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { CornerFrame } from "@/components/panels/CornerFrame"
import { HelpTooltip } from "@/components/shared/HelpTooltip"
import { ColorPicker } from "@/components/shared/ColorPicker"
import { cn } from "@/lib/utils"
import { bridge, type AppSettings, type Language, type ModelEntry, type SearchConfig } from "@/lib/api"
import { levelAtLeast, type ExperienceLevel } from "@/lib/use-experience"
import { setHelpTooltipsEnabled, useHelpTooltipsEnabled } from "@/lib/use-help-tooltips"
import { setAccentColor, resetAccentColor, useAccentColor } from "@/lib/use-accent-color"
import { startTour } from "@/lib/use-tour"
import { confirmAction } from "@/lib/use-confirm"
import { createSettingsSaver } from "@/lib/settings-save"

const SEARCH_PROVIDERS = [
  { value: "none", label: "None (Hugging Face ranking only)" },
  { value: "google_cse", label: "Google Programmable Search" },
]

const QUALITY_STEPS = [1, 2, 4]

async function showSettingsError(error: unknown) {
  await confirmAction({
    title: "Settings could not be saved or loaded",
    description: String(error instanceof Error ? error.message : error),
    alertOnly: true,
  })
}

interface SettingsPageProps {
  level: ExperienceLevel
}

export function SettingsPage({ level }: SettingsPageProps) {
  const [values, setValues] = useState<AppSettings | null>(null)
  const [whisperSizes, setWhisperSizes] = useState<string[]>([])
  const [isolatedSpeechReady, setIsolatedSpeechReady] = useState(false)
  const [isolatedRecognitionReady, setIsolatedRecognitionReady] = useState(false)
  const [isolatedTranslationReady, setIsolatedTranslationReady] = useState(false)
  const [isolatedFallbackReady, setIsolatedFallbackReady] = useState(false)
  const [isolatedSeparationReady, setIsolatedSeparationReady] = useState(false)
  const [isolatedEnhancementReady, setIsolatedEnhancementReady] = useState(false)
  const [voices, setVoices] = useState<ModelEntry[]>([])
  const [saved, setSaved] = useState(false)
  const [enqueueSettingsSave] = useState(() => createSettingsSaver())
  const [searchConfig, setSearchConfig] = useState<SearchConfig | null>(null)
  const [searchProvider, setSearchProvider] = useState("none")
  const [searchEngineId, setSearchEngineId] = useState("")
  const [searchApiKey, setSearchApiKey] = useState("")
  const [searchSaved, setSearchSaved] = useState<string | null>(null)
  const [languages, setLanguages] = useState<Language[]>([])
  const [dialogueConnections, setDialogueConnections] = useState<ModelEntry[]>([])
  const [dialogueStatus, setDialogueStatus] = useState('')
  const [dialogueReadiness, setDialogueReadiness] = useState('off')

  useEffect(() => {
    bridge.getSettings().then((res) => {
      setValues(res.values)
      setWhisperSizes(res.whisper_model_sizes)
      setIsolatedSpeechReady(res.xtts_runtime_status === 'ready-for-explicit-trial')
      setIsolatedRecognitionReady(res.recognition_runtime_status === 'ready-for-explicit-trial')
      setIsolatedTranslationReady(res.nllb_runtime_status === 'ready-for-explicit-trial')
      setIsolatedFallbackReady(res.m2m100_runtime_status === 'ready-for-explicit-trial')
      setIsolatedSeparationReady(res.separation_runtime_status === 'ready-for-explicit-trial')
      setIsolatedEnhancementReady(res.enhancement_runtime_status === 'ready-for-explicit-trial')
    }).catch(showSettingsError)
    bridge.listModels("voice").then((models) => setVoices(models.filter((m) => m.status === "installed")))
    bridge.listLanguages().then(setLanguages)
    bridge.listModels('translation').then((models) => setDialogueConnections(models.filter(
      (m) => m.status === 'installed' && m.kind !== 'local_file' && m.request_preset === 'openai_chat'
    ))).catch(showSettingsError)
    bridge.getSearchConfig().then((cfg) => {
      setSearchConfig(cfg)
      setSearchProvider(cfg.provider)
      setSearchEngineId(cfg.engine_id)
    })
  }, [])

  useEffect(() => {
    if (!values) return
    let active = true
    bridge.getDialogueReadiness().then((status) => {
      if (active) { setDialogueStatus(status.message); setDialogueReadiness(status.status) }
    }).catch((error: unknown) => { if (active) setDialogueStatus(String(error)) })
    return () => { active = false }
  }, [values])

  async function handleSaveSearch() {
    const result = await bridge.setSearchCredentials(searchProvider, searchApiKey, searchEngineId)
    if (result.ok) {
      setSearchApiKey("")
      setSearchSaved("Saved")
      bridge.getSearchConfig().then(setSearchConfig)
    } else {
      setSearchSaved(result.message ?? "Failed to save")
    }
    setTimeout(() => setSearchSaved(null), 2000)
  }

  async function patch(partial: Partial<AppSettings>) {
    if (!values) return
    try {
      const persisted = await enqueueSettingsSave(() => bridge.updateSettings(partial))
      setValues(persisted)
      setSaved(true)
      setTimeout(() => setSaved(false), 1200)
    } catch (error) {
      setSaved(false)
      await showSettingsError(error)
    }
  }

  async function handleReset() {
    const ok = await confirmAction({
      title: "Reset all settings to defaults?",
      description:
        "This resets every setting on this page - including your default language, voice, pipeline defaults, and engine hosts - back to factory defaults. It also brings back the first-run setup wizard on next launch. This can't be undone.",
      confirmLabel: "Reset Settings",
      destructive: true,
    })
    if (!ok) return
    try {
      const restored = await enqueueSettingsSave(() => bridge.resetSettings())
      setValues(restored)
    } catch (error) {
      await showSettingsError(error)
    }
  }

  // Both hooks below must run on every render, in the same order - React's
  // Rules of Hooks - so they're called before the `!values` early return,
  // not after it. Calling them after meant the very first render (values
  // still null, before bridge.getSettings() resolves) skipped both hooks
  // entirely, while every later render called them - a hook-count
  // mismatch React detects and throws a hard error for, crashing this
  // page's whole render tree with nothing left on screen but the app's
  // dark background ("the window goes black" opening Settings).
  const tooltipsEnabled = useHelpTooltipsEnabled()
  const { color: accentColor } = useAccentColor()

  if (!values) {
    return <div className="p-6 text-sm text-muted-foreground">Loading settings…</div>
  }

  const isAdvanced = levelAtLeast(level, "advanced")
  const isExpert = levelAtLeast(level, "expert")

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>
          SETTINGS
        </h1>
        {saved && <span className="text-xs text-success">Saved</span>}
      </div>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-sm">00 // INTERFACE</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-6 md:grid-cols-[1fr_auto]">
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-sm">Show help ("?") tooltips</span>
                <HelpTooltip text='Controls the small "?" icons shown next to settings and controls across every page. Turning this off hides all of them, everywhere.' />
              </div>
              <Switch checked={tooltipsEnabled} onCheckedChange={setHelpTooltipsEnabled} />
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-sm">Product tour</span>
                <HelpTooltip text='Replays the spotlight walkthrough shown after first-run setup - same tour, run again anytime ("demo mode").' />
              </div>
              <Button variant="outline" size="sm" onClick={startTour}>Replay Tour</Button>
            </div>
          </div>
          <div className="flex flex-col items-center gap-2 md:border-l md:border-border md:pl-6">
            <div className="flex items-center gap-1.5 self-start">
              <span className="text-xs text-muted-foreground">Accent Color</span>
              <HelpTooltip text="Changes the app's primary accent color everywhere it's used - buttons, highlights, glows, the active nav item. Drag the ring for hue, the square for saturation/brightness, or type an exact hex code." />
            </div>
            <ColorPicker value={accentColor} onChange={setAccentColor} onReset={resetAccentColor} />
          </div>
        </CardContent>
      </Card>

      <div className={cn("grid grid-cols-1 gap-4", isAdvanced ? "xl:grid-cols-2" : "xl:grid-cols-2 xl:max-w-2xl")}>
        <CornerFrame>
          <Card className="h-full border-border bg-card">
            <CardHeader>
              <CardTitle className="text-sm">01 // DEFAULTS</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">Default Language</span>
                  <HelpTooltip text="The language every new render defaults to translating into. Change it per-render on the Dashboard anytime." />
                </div>
                <Select value={values.default_language} onValueChange={(v) => patch({ default_language: v })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {languages.map(({ code, name }) => (
                      <SelectItem key={code} value={code}>{name} ({code})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">Default Voice Model</span>
                  <HelpTooltip text="Which installed voice a new render uses to speak, unless you pick a different one for that render." />
                </div>
                <Select value={values.default_voice} onValueChange={(v) => patch({ default_voice: v })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {voices.map((v) => (
                      <SelectItem key={v.id} value={v.display_name}>{v.display_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </CornerFrame>

        {isAdvanced && (
          <Card className="h-full border-border bg-card">
            <CardHeader>
              <CardTitle className="text-sm">02 // PIPELINE DEFAULTS</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div className="flex flex-col gap-2">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span>Default Task Priority</span>
                    <HelpTooltip text="Trades render speed for output quality. Lower favors a faster ffmpeg encode preset; higher favors quality." />
                  </div>
                  <span className="text-primary">{values.default_task_priority}</span>
                </div>
                <Slider
                  value={[values.default_task_priority]}
                  onValueChange={([v]) => patch({ default_task_priority: v })}
                  max={100}
                  step={1}
                />
              </div>
              <div className="flex flex-col gap-2">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span>Default Texture Quality</span>
                    <HelpTooltip text="Upscale factor applied by the Face Enhancer stage when it's enabled. Higher looks better but takes longer and uses more VRAM." />
                  </div>
                  <span className="text-primary">{values.default_texture_quality}x</span>
                </div>
                <Slider
                  value={[QUALITY_STEPS.indexOf(values.default_texture_quality)]}
                  onValueChange={([i]) => patch({ default_texture_quality: QUALITY_STEPS[i] })}
                  max={QUALITY_STEPS.length - 1}
                  step={1}
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm">Preserve Background by default</span>
                  <HelpTooltip text="Separates and keeps the original background music/ambience, mixing your new dubbed voice track on top of it instead of replacing the whole audio track." />
                </div>
                <Switch checked={values.keep_bg_default} onCheckedChange={(v) => patch({ keep_bg_default: v })} />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm">Content Filter by default</span>
                  <HelpTooltip text="Runs the active Visual Filter model over every frame to detect and blur unsafe content before the final render is saved." />
                </div>
                <Switch
                  checked={values.content_filter_default}
                  onCheckedChange={(v) => patch({ content_filter_default: v })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">Auto-clean temp files after each render</span>
                    <HelpTooltip text="Sweeps the temp/ folder once a job finishes or fails, so intermediate audio/video files don't accumulate on disk." />
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Sweeps the temp/ folder once a job finishes or fails.
                  </div>
                </div>
                <Switch
                  checked={values.auto_cleanup_temp}
                  onCheckedChange={(v) => patch({ auto_cleanup_temp: v })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">Auto-detect model type in Marketplace</span>
                    <HelpTooltip text="Guess the stage (STT, TTS, Voice, etc.) from a pasted link instead of picking a tab first. Always shown as a suggestion to confirm, never applied automatically." />
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Guess the stage (STT, TTS, Voice, etc.) from a pasted link instead of
                    picking a tab first. Always shown as a suggestion to confirm.
                  </div>
                </div>
                <Switch
                  checked={values.auto_detect_model_type}
                  onCheckedChange={(v) => patch({ auto_detect_model_type: v })}
                />
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <Card className="border-border bg-card">
        <CardHeader><CardTitle className="text-sm">Dialogue assistance</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-xs text-muted-foreground">Optional connections for shorter wording and meaning review in saved cue reviews. Your active translator and voice stay selected. Requests require your action; automatic rewriting is not enabled.</p>
          <label className="flex flex-col gap-1.5 text-xs">
            Assistance mode
            <Select value={values.dialogue_mode} onValueChange={(mode) => patch({ dialogue_mode: mode as AppSettings['dialogue_mode'] })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="off">Off</SelectItem>
                <SelectItem value="local">Local assistance on this computer</SelectItem>
                <SelectItem value="hybrid">Hybrid assistance with selected APIs</SelectItem>
              </SelectContent>
            </Select>
          </label>
          {values.dialogue_mode !== 'off' && <>
            <p className="text-xs text-muted-foreground">Add a chat-compatible connection with an explicit model in Marketplace → Translation. You do not need to set it as the active translator. Saving these choices makes no model requests.</p>
            {(['writer', 'reviewer'] as const).map((role) => {
              const key = role === 'writer' ? 'dialogue_writer_id' : 'dialogue_reviewer_id'
              return <label key={role} className="flex flex-col gap-1.5 text-xs">
                {role === 'writer' ? 'Dialogue writer' : 'Meaning reviewer'}
                <Select value={values[key] || 'none'} onValueChange={(id) => patch({ [key]: id === 'none' ? '' : id })}>
                  <SelectTrigger><SelectValue placeholder="Choose a connection" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Choose a connection</SelectItem>
                    {dialogueConnections.map((entry) => <SelectItem key={entry.id} value={entry.id}>{entry.display_name} · {entry.api_base_url}</SelectItem>)}
                  </SelectContent>
                </Select>
              </label>
            })}
            {values.dialogue_mode === 'hybrid' && <div className="flex items-center justify-between gap-4">
              <p className="text-xs">Allow the selected connections to receive original and translated dialogue, candidate wording and timing estimates. Provider usage charges may apply. Video and audio are not sent by this feature.</p>
              <Switch checked={values.dialogue_text_consent && dialogueReadiness !== 'needs_consent'} onCheckedChange={(consent) => patch({ dialogue_text_consent: consent })} />
            </div>}
            <p className="text-xs text-muted-foreground">Writer and reviewer can use the same connection, but agreement is not independent proof. Suggestions remain subject to review. There is no automatic cloud fallback.</p>
          </>}
          <p className="text-xs" role="status">{dialogueStatus}</p>
        </CardContent>
      </Card>

      {isExpert && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-sm">03 // EXPERT</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">
                    Ollama Host (LLM translation - falls back to offline M2M100 if unreachable)
                  </span>
                  <HelpTooltip text="Base URL of a locally-running Ollama server used for the default translation engine. If it can't be reached, translation falls back to the bundled offline M2M100 model automatically." />
                </div>
                <Input
                  value={values.ollama_host}
                  onChange={(e) => setValues({ ...values, ollama_host: e.target.value })}
                  onBlur={() => patch({ ollama_host: values.ollama_host })}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">Whisper Model Size (transcription)</span>
                  <HelpTooltip text="Which local Whisper checkpoint transcribes speech to text. Larger sizes are more accurate but slower, especially on CPU." />
                </div>
                <Select
                  value={values.whisper_model_size}
                  onValueChange={(v) => patch({ whisper_model_size: v })}
                >
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {whisperSizes.map((size) => (
                      <SelectItem key={size} value={size}>{size}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <span className="text-[11px] text-muted-foreground">
                  Larger = more accurate, slower on CPU.
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">CPU recognition runtime</span>
                <Select value={values.recognition_runtime ?? 'legacy'} onValueChange={(v) => patch({ recognition_runtime: v as AppSettings['recognition_runtime'] })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="legacy">Current runtime</SelectItem>
                    <SelectItem value="isolated" disabled={!isolatedRecognitionReady}>Isolated CPU runtime (trial)</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-[11px] text-muted-foreground">
                  Uses the selected CPU recognition model in a separate environment. GPU recognition and API connections keep their own routes.
                  {!isolatedRecognitionReady && ' The isolated runtime is unavailable in this installation.'}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">NLLB translation runtime</span>
                <Select value={values.nllb_runtime ?? 'legacy'} onValueChange={(v) => patch({ nllb_runtime: v as AppSettings['nllb_runtime'] })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="legacy">Current runtime</SelectItem>
                    <SelectItem value="isolated" disabled={!isolatedTranslationReady}>Isolated CPU runtime (trial)</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-[11px] text-muted-foreground">
                  Applies to connected NLLB models. Uses the existing modern CPU environment in a separate process. Other translation engines keep their own routes.
                  {!isolatedTranslationReady && ' The isolated runtime is unavailable in this installation.'}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">M2M100 fallback runtime</span>
                <Select value={values.m2m100_runtime ?? 'legacy'} onValueChange={(v) => patch({ m2m100_runtime: v as AppSettings['m2m100_runtime'] })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="legacy">Current runtime</SelectItem>
                    <SelectItem value="isolated" disabled={!isolatedFallbackReady}>Isolated CPU runtime (trial)</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-[11px] text-muted-foreground">
                  Applies when the built-in Ollama translator falls back to M2M100. Uses existing local weights in a separate process. Connected translation engines keep their own routes.
                  {!isolatedFallbackReady && ' The isolated fallback is unavailable in this installation.'}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">Background separation runtime</span>
                <Select value={values.separation_runtime ?? 'legacy'} onValueChange={(v) => patch({ separation_runtime: v as AppSettings['separation_runtime'] })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="legacy">Current runtime</SelectItem>
                    <SelectItem value="isolated" disabled={!isolatedSeparationReady}>Isolated CPU runtime (trial)</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-[11px] text-muted-foreground">Used when preserving background audio. Uses the existing Demucs model in a separate CPU process.
                  {!isolatedSeparationReady && ' The isolated separation runtime is unavailable in this installation.'}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">Face enhancement runtime</span>
                <Select value={values.enhancement_runtime ?? 'legacy'} onValueChange={(v) => patch({ enhancement_runtime: v as AppSettings['enhancement_runtime'] })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="legacy">Current runtime</SelectItem>
                    <SelectItem value="isolated" disabled={!isolatedEnhancementReady}>Isolated CPU runtime (trial)</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-[11px] text-muted-foreground">Used when face enhancement is enabled. Runs the existing GFPGAN model in a separate CPU process.
                  {!isolatedEnhancementReady && ' The isolated face enhancement runtime is unavailable in this installation.'}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">XTTS speech runtime</span>
                <Select value={values.xtts_runtime ?? 'legacy'} onValueChange={(v) => patch({ xtts_runtime: v as AppSettings['xtts_runtime'] })}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="legacy">Current runtime</SelectItem>
                    <SelectItem value="isolated" disabled={!isolatedSpeechReady}>Isolated CPU runtime (trial)</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-[11px] text-muted-foreground">
                  Applies to XTTS voices. Choose CPU in the render controls for the isolated trial. Other speech engines keep their own runtime.
                  {!isolatedSpeechReady && ' The isolated runtime is unavailable in this installation.'}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <CardTitle className="text-sm">04 // WEB SEARCH (AUTO MODEL PICK)</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <p className="text-[11px] text-muted-foreground">
                Marketplace's "Auto-pick best model" always ranks Hugging Face models by
                downloads - no setup needed. Configuring a search provider here adds extra
                web-search suggestions on top of that (candidates to review, never
                auto-installed).
              </p>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">Provider</span>
                  <HelpTooltip text="Which search API, if any, supplements Hugging Face's download-count ranking with extra web-search candidates for Auto-pick." />
                </div>
                <Select value={searchProvider} onValueChange={setSearchProvider}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {SEARCH_PROVIDERS.map((p) => (
                      <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {searchProvider !== "none" && (
                <>
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground">Search Engine ID (cx)</span>
                      <HelpTooltip text="Google Programmable Search's Custom Search Engine identifier - not secret, safe to store in plain settings." />
                    </div>
                    <Input value={searchEngineId} onChange={(e) => setSearchEngineId(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground">
                        API Key {searchConfig?.configured && "(already saved - leave blank to keep it)"}
                      </span>
                      <HelpTooltip text="Stored in your OS credential manager, never in a plain settings file." />
                    </div>
                    <Input
                      type="password"
                      value={searchApiKey}
                      onChange={(e) => setSearchApiKey(e.target.value)}
                      placeholder={searchConfig?.configured ? "••••••••" : ""}
                    />
                  </div>
                </>
              )}
              <div className="flex items-center gap-2">
                <Button size="sm" onClick={handleSaveSearch} className="self-start">Save</Button>
                {searchSaved && <span className="text-xs text-success">{searchSaved}</span>}
              </div>
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader>
              <div className="flex items-center gap-1.5">
                <CardTitle className="text-sm">05 // RAW SETTINGS</CardTitle>
                <HelpTooltip text="The exact contents of settings.json, live - useful for confirming a change actually saved." />
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <pre
                className="max-h-64 overflow-auto rounded-md border border-border bg-muted/30 p-3 text-[11px] text-muted-foreground"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {JSON.stringify(values, null, 2)}
              </pre>
              <Button variant="outline" size="sm" onClick={handleReset} className="self-start">
                Reset to Defaults
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {!isAdvanced && (
        <p className="text-center text-xs text-muted-foreground">
          Switch to ADVANCED or EXPERT (top right) for pipeline defaults and
          engine-level configuration.
        </p>
      )}
    </div>
  )
}
