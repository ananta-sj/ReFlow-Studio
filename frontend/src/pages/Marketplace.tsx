import { useEffect, useState } from "react"
import { Cloud, Cpu, Download, HardDrive, Server, Sparkles, Star, Trash2, Wand2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { HelpTooltip } from "@/components/shared/HelpTooltip"
import { CueAudioPlayer } from "@/components/shared/CueAudioPlayer"
import { useMarketplace } from "@/lib/use-marketplace"
import { cn } from "@/lib/utils"
import {
  bridge,
  type BestModelResult,
  type ModelEntry,
  type ModelTypeDetection,
  type RecommendedModel,
  type StageType,
  type HindiVoiceLibrary,
} from "@/lib/api"

const STAGE_TABS: { id: StageType; label: string }[] = [
  { id: "stt", label: "STT" },
  { id: "translation", label: "Translation" },
  { id: "tts", label: "TTS" },
  { id: "voice", label: "Voice" },
  { id: "enhancer", label: "Enhancer" },
  { id: "filter", label: "Visual Filter" },
  { id: "lipsync", label: "Lipsync" },
  { id: "profanity_filter", label: "Profanity Filter" },
]

// Named request presets per stage type - "custom" always covers anything
// else via a user-supplied endpoint (see core/providers/*/cloud_rest.py).
const CLOUD_PRESETS: Record<StageType, { value: string; label: string }[]> = {
  stt: [
    { value: "openai_whisper", label: "OpenAI Whisper-compatible" },
    { value: "custom", label: "Custom" },
  ],
  translation: [
    { value: "openai_chat", label: "OpenAI-compatible Chat (also fits Ollama /v1, LM Studio, etc.)" },
    { value: "custom", label: "Custom" },
  ],
  tts: [
    { value: "openai_tts", label: "OpenAI TTS-compatible" },
    { value: "elevenlabs_tts", label: "ElevenLabs" },
    { value: "custom", label: "Custom" },
  ],
  voice: [
    { value: "elevenlabs_sts", label: "ElevenLabs Speech-to-Speech" },
    { value: "custom", label: "Custom" },
  ],
  enhancer: [{ value: "custom", label: "Custom" }],
  filter: [{ value: "custom", label: "Custom" }],
  lipsync: [{ value: "custom", label: "Custom" }],
  profanity_filter: [
    { value: "openai_chat", label: "OpenAI-compatible Chat (also fits Ollama /v1, LM Studio, etc.)" },
    { value: "custom", label: "Custom" },
  ],
}

// Only these two stages are backed by an instructable model (an LLM chat
// call), so only they get an editable "custom instructions" box on their
// model cards - see core/providers/base.py's TranslationProvider/
// ProfanityFilterProvider docstrings for why the rest can't honor one.
const INSTRUCTABLE_STAGES: StageType[] = ["translation", "profanity_filter"]

function formatSpeed(bps: number) {
  if (bps > 1024 * 1024) return `${(bps / (1024 * 1024)).toFixed(1)} MB/s`
  return `${(bps / 1024).toFixed(0)} KB/s`
}

function formatEta(seconds: number | null) {
  if (seconds == null) return ""
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return m > 0 ? `${m}m ${s}s left` : `${s}s left`
}

function kindBadge(kind: ModelEntry["kind"]) {
  if (kind === "local_file") return { icon: HardDrive, label: "Local" }
  if (kind === "local_api") return { icon: Server, label: "Local API" }
  return { icon: Cloud, label: "Cloud" }
}

function AutoPickSection({ stageType, onPick }: { stageType: StageType; onPick: (name: string, url: string) => void }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BestModelResult | null>(null)

  async function runAutoPick() {
    setLoading(true)
    setResult(null)
    const r = await bridge.findBestModel(stageType)
    setLoading(false)
    setResult(r)
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-border p-3">
      <Button type="button" size="sm" variant="secondary" onClick={runAutoPick} disabled={loading}>
        <Wand2 className="mr-1 h-3.5 w-3.5" /> {loading ? "Searching…" : "Find compatible models"}
      </Button>
      {result && result.hf_picks.length === 0 && result.web_results.length === 0 && (
        <p className="text-[11px] text-muted-foreground">No candidates found - try Local Download manually.</p>
      )}
      {result && result.hf_picks.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-muted-foreground">Implemented adapters - ranked by downloads</span>
          {result.hf_picks.map((p) => (
            <button
              key={p.repo_id}
              type="button"
              onClick={() => onPick(p.repo_id, p.url)}
              className="flex items-center justify-between rounded-md border border-border px-2 py-1.5 text-left text-xs hover:border-primary/50"
            >
              <span className="truncate">{p.repo_id}</span>
              <span className="shrink-0 text-muted-foreground">{p.downloads.toLocaleString()} downloads</span>
            </button>
          ))}
        </div>
      )}
      {result && result.web_results.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-muted-foreground">Web search suggestions</span>
          {result.web_results.map((w) => (
            <button
              key={w.link}
              type="button"
              onClick={() => onPick(w.title, w.link)}
              className="flex flex-col rounded-md border border-border px-2 py-1.5 text-left text-xs hover:border-primary/50"
            >
              <span className="truncate font-medium">{w.title}</span>
              <span className="truncate text-[11px] text-muted-foreground">{w.link}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

interface AddModelPrefill {
  tab: "local" | "cloud"
  name: string
  url: string
  preset?: string
}

function AddModelDialog({
  stageType,
  mp,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
  hideTrigger,
  prefill,
}: {
  stageType: StageType
  mp: ReturnType<typeof useMarketplace>
  open?: boolean
  onOpenChange?: (open: boolean) => void
  hideTrigger?: boolean
  prefill?: AddModelPrefill | null
}) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false)
  const open = controlledOpen ?? uncontrolledOpen
  const setOpen = controlledOnOpenChange ?? setUncontrolledOpen
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<"local" | "cloud" | "localapi" | "airllm">("local")

  const [localName, setLocalName] = useState("")
  const [localUrl, setLocalUrl] = useState("")
  const [localPreset, setLocalPreset] = useState<string | null>(null)

  const [cloudName, setCloudName] = useState("")
  const [cloudUrl, setCloudUrl] = useState("")
  const [cloudKey, setCloudKey] = useState("")
  const [cloudPreset, setCloudPreset] = useState(CLOUD_PRESETS[stageType][0].value)
  const [cloudConfig, setCloudConfig] = useState("{}")
  const [serviceVoiceId, setServiceVoiceId] = useState("")

  const [apiName, setApiName] = useState("")
  const [apiUrl, setApiUrl] = useState("")
  const [apiConfig, setApiConfig] = useState("{}")

  function parseServiceConfig(raw: string): Record<string, unknown> | null {
    try {
      const value: unknown = JSON.parse(raw)
      if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error()
      return value as Record<string, unknown>
    } catch {
      setError("Service configuration must be a JSON object.")
      return null
    }
  }

  const [airllmName, setAirllmName] = useState("")
  const [airllmModelId, setAirllmModelId] = useState("")
  const [airllmCompression, setAirllmCompression] = useState("4bit")

  useEffect(() => {
    if (!prefill) return
    setSource(prefill.tab)
    if (prefill.tab === "local") {
      setLocalName(prefill.name)
      setLocalUrl(prefill.url)
      setLocalPreset(prefill.preset ?? null)
    } else {
      setCloudName(prefill.name)
      setCloudUrl(prefill.url)
      if (prefill.preset) setCloudPreset(prefill.preset)
    }
  }, [prefill])

  function resetAndClose() {
    setSource("local")
    setLocalName(""); setLocalUrl(""); setLocalPreset(null)
    setCloudName(""); setCloudUrl(""); setCloudKey("")
    setCloudConfig("{}"); setServiceVoiceId("")
    setApiName(""); setApiUrl("")
    setApiConfig("{}")
    setAirllmName(""); setAirllmModelId(""); setAirllmCompression("4bit")
    setError(null)
    setOpen(false)
  }

  async function submitLocal() {
    if (!localUrl.trim() || !localName.trim()) return
    setBusy(true); setError(null)
    const result = await mp.addLocal(localUrl.trim(), localName.trim(), localPreset)
    setBusy(false)
    if (result.ok) resetAndClose()
    else setError(result.message ?? "Failed to start download.")
  }

  async function submitCloud() {
    if (!cloudUrl.trim() || !cloudName.trim() || !cloudKey.trim()) return
    const config = parseServiceConfig(cloudConfig)
    if (!config) return
    if (cloudPreset.startsWith("elevenlabs_") && !serviceVoiceId.trim()) {
      setError("Enter the voice ID supplied by ElevenLabs.")
      return
    }
    setBusy(true); setError(null)
    const result = await mp.addCloud(cloudName.trim(), cloudUrl.trim(), cloudKey.trim(), cloudPreset,
      { ...config, ...(serviceVoiceId.trim() ? { voice_id: serviceVoiceId.trim() } : {}) })
    setBusy(false)
    if (result.ok) resetAndClose()
    else setError(result.message ?? "Failed to add cloud model.")
  }

  async function submitLocalApi() {
    if (!apiUrl.trim() || !apiName.trim()) return
    const config = parseServiceConfig(apiConfig)
    if (!config) return
    setBusy(true); setError(null)
    const result = await mp.addLocalApi(apiName.trim(), apiUrl.trim(), "custom", config)
    setBusy(false)
    if (result.ok) resetAndClose()
    else setError(result.message ?? "Failed to add local service.")
  }

  async function submitAirllm() {
    if (!airllmModelId.trim() || !airllmName.trim()) return
    setBusy(true); setError(null)
    const result = await bridge.addAirllmModel(airllmName.trim(), airllmModelId.trim(), airllmCompression)
    setBusy(false)
    if (result.ok) { await mp.refresh(); resetAndClose() }
    else setError(result.message ?? "Failed to add AirLLM model.")
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {!hideTrigger && (
        <DialogTrigger asChild>
          <Button size="sm" variant="outline"><Download className="mr-1 h-3.5 w-3.5" /> Add Model</Button>
        </DialogTrigger>
      )}
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>Add {STAGE_TABS.find((t) => t.id === stageType)?.label} Model</DialogTitle></DialogHeader>
        <Tabs value={source} onValueChange={(v) => setSource(v as typeof source)}>
          <TabsList className={cn("grid w-full", stageType === "translation" ? "grid-cols-4" : "grid-cols-3")}>
            <TabsTrigger value="local" className="gap-1">
              Local Download <HelpTooltip text="Downloads a model file/repo onto this machine and runs it locally - no API key needed." />
            </TabsTrigger>
            <TabsTrigger value="cloud" className="gap-1">
              Cloud API <HelpTooltip text="Connects to a paid/keyed cloud service instead of running anything locally." />
            </TabsTrigger>
            <TabsTrigger value="localapi" className="gap-1">
              Local Service <HelpTooltip text="Connects to a service already running on your machine or network (e.g. Ollama) - no API key needed." />
            </TabsTrigger>
            {stageType === "translation" && (
              <TabsTrigger value="airllm" className="gap-1">
                AirLLM <HelpTooltip text="Runs a full Hugging Face model with layer-by-layer disk offloading - slower, but works on hardware too small to load the model normally." />
              </TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="local" className="flex flex-col gap-3 pt-2">
            <AutoPickSection
              stageType={stageType}
              onPick={(name, url) => { setLocalName(name); setLocalUrl(url) }}
            />
            <Input placeholder="Display name" value={localName} onChange={(e) => setLocalName(e.target.value)} />
            <Input
              placeholder="Model URL (Hugging Face link, .zip, .pth, etc.)"
              value={localUrl}
              onChange={(e) => setLocalUrl(e.target.value)}
            />
            <Button onClick={submitLocal} disabled={busy}>{busy ? "Starting…" : "Download & Install"}</Button>
          </TabsContent>

          <TabsContent value="cloud" className="flex flex-col gap-3 pt-2">
            <Input placeholder="Display name" value={cloudName} onChange={(e) => setCloudName(e.target.value)} />
            <Input placeholder="API base URL (e.g. https://api.openai.com)" value={cloudUrl} onChange={(e) => setCloudUrl(e.target.value)} />
            <Input placeholder="API key" type="password" value={cloudKey} onChange={(e) => setCloudKey(e.target.value)} />
            <Select value={cloudPreset} onValueChange={setCloudPreset}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {CLOUD_PRESETS[stageType].map((p) => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {cloudPreset.startsWith("elevenlabs_") && (
              <Input aria-label="Service voice ID" placeholder="ElevenLabs voice ID" value={serviceVoiceId} onChange={(e) => setServiceVoiceId(e.target.value)} />
            )}
            <details className="text-xs text-muted-foreground">
              <summary>Advanced service configuration</summary>
              <p className="py-2">Optional model, endpoint and response settings as JSON. Keep API keys in the password field above.</p>
              <Textarea aria-label="Cloud service configuration" value={cloudConfig} onChange={(e) => setCloudConfig(e.target.value)} />
            </details>
            <p className="text-[11px] text-muted-foreground">
              The API key is stored in your OS credential manager, never in a plain settings file.
            </p>
            <Button onClick={submitCloud} disabled={busy}>{busy ? "Adding…" : "Add Cloud Model"}</Button>
          </TabsContent>

          <TabsContent value="localapi" className="flex flex-col gap-3 pt-2">
            <Input placeholder="Display name" value={apiName} onChange={(e) => setApiName(e.target.value)} />
            <Input
              placeholder="Base URL (e.g. http://localhost:11434)"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
            />
            <p className="text-[11px] text-muted-foreground">
              For self-hosted / local network services that need no API key (Ollama-style).
            </p>
            <Button onClick={submitLocalApi} disabled={busy}>{busy ? "Adding…" : "Add Local Service"}</Button>
            <details className="text-xs text-muted-foreground">
              <summary>Advanced service configuration</summary>
              <p className="py-2">Optional endpoint and response settings as JSON.</p>
              <Textarea aria-label="Local service configuration" value={apiConfig} onChange={(e) => setApiConfig(e.target.value)} />
            </details>
          </TabsContent>

          {stageType === "translation" && (
            <TabsContent value="airllm" className="flex flex-col gap-3 pt-2">
              <p className="text-[11px] text-muted-foreground">
                Runs a full Hugging Face model with layer-by-layer disk offloading - much
                slower than the default translator, but works on hardware too small to load
                the model normally. Never used unless you add one here and set it Active.
              </p>
              <Input placeholder="Display name" value={airllmName} onChange={(e) => setAirllmName(e.target.value)} />
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
              <Button onClick={submitAirllm} disabled={busy}>{busy ? "Adding…" : "Add AirLLM Model"}</Button>
            </TabsContent>
          )}
        </Tabs>
        {error && <p className="text-xs text-destructive">{error}</p>}
      </DialogContent>
    </Dialog>
  )
}

function QuickAddDialog() {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detection, setDetection] = useState<ModelTypeDetection | null>(null)
  const [stageType, setStageType] = useState<StageType>("voice")

  const [source, setSource] = useState<"local" | "cloud" | "localapi">("local")
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [apiUrl, setApiUrl] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [preset, setPreset] = useState("custom")
  const [serviceConfig, setServiceConfig] = useState("{}")
  const [serviceVoiceId, setServiceVoiceId] = useState("")

  function reset() {
    setName(""); setUrl(""); setApiUrl(""); setApiKey(""); setPreset("custom")
    setServiceConfig("{}"); setServiceVoiceId("")
    setDetection(null); setError(null); setOpen(false)
  }

  async function runDetection() {
    const link = source === "local" ? url.trim() : apiUrl.trim()
    if (!link) return
    setDetecting(true)
    const result = await bridge.detectModelType(link, source === "local" ? "url" : "api_base_url")
    setDetecting(false)
    setDetection(result)
    if (result.stage_type) setStageType(result.stage_type)
  }

  async function submit() {
    if (!name.trim()) return
    setBusy(true); setError(null)
    let config: Record<string, unknown> = {}
    if (source !== "local") {
      try {
        const parsed: unknown = JSON.parse(serviceConfig)
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error()
        config = parsed as Record<string, unknown>
      } catch {
        setError("Service configuration must be a JSON object."); setBusy(false); return
      }
      if (source === "cloud" && preset.startsWith("elevenlabs_") && !serviceVoiceId.trim()) {
        setError("Enter the ElevenLabs voice ID for this connection."); setBusy(false); return
      }
      if (serviceVoiceId.trim()) config.voice_id = serviceVoiceId.trim()
    }
    let result
    if (source === "local") {
      if (!url.trim()) { setBusy(false); return }
      result = await bridge.addLocalModel(stageType, url.trim(), name.trim())
    } else if (source === "cloud") {
      if (!apiUrl.trim() || !apiKey.trim()) { setBusy(false); return }
      result = await bridge.addCloudModel(stageType, name.trim(), apiUrl.trim(), apiKey.trim(), preset, config)
    } else {
      if (!apiUrl.trim()) { setBusy(false); return }
      result = await bridge.addLocalApiModel(stageType, name.trim(), apiUrl.trim(), "custom", config)
    }
    setBusy(false)
    if (result.ok) reset()
    else setError(result.message ?? "Failed to add model.")
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset() }}>
      <DialogTrigger asChild>
        <Button size="sm"><Sparkles className="mr-1 h-3.5 w-3.5" /> Quick Add (Auto-detect)</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>Quick Add Model</DialogTitle></DialogHeader>
        <Tabs value={source} onValueChange={(v) => { setSource(v as typeof source); setDetection(null) }}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="local">Local Download</TabsTrigger>
            <TabsTrigger value="cloud">Cloud API</TabsTrigger>
            <TabsTrigger value="localapi">Local Service</TabsTrigger>
          </TabsList>

          <TabsContent value="local" className="flex flex-col gap-3 pt-2">
            <AutoPickSection
              stageType={stageType}
              onPick={(pickedName, pickedUrl) => {
                setName(pickedName)
                setUrl(pickedUrl)
                setDetection({ stage_type: stageType, confidence: "high", reason: "From Auto-pick" })
              }}
            />
            <Input placeholder="Display name" value={name} onChange={(e) => setName(e.target.value)} />
            <div className="flex gap-2">
              <Input
                placeholder="Model URL (Hugging Face link, .zip, .pth, etc.)"
                value={url}
                onChange={(e) => { setUrl(e.target.value); setDetection(null) }}
                onBlur={runDetection}
              />
              <Button type="button" variant="outline" size="sm" onClick={runDetection} disabled={detecting || !url.trim()}>
                {detecting ? "…" : "Detect"}
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="cloud" className="flex flex-col gap-3 pt-2">
            <Input placeholder="Display name" value={name} onChange={(e) => setName(e.target.value)} />
            <div className="flex gap-2">
              <Input
                placeholder="API base URL (e.g. https://api.openai.com)"
                value={apiUrl}
                onChange={(e) => { setApiUrl(e.target.value); setDetection(null) }}
                onBlur={runDetection}
              />
              <Button type="button" variant="outline" size="sm" onClick={runDetection} disabled={detecting || !apiUrl.trim()}>
                {detecting ? "…" : "Detect"}
              </Button>
            </div>
            <Input placeholder="API key" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
            <Select value={preset} onValueChange={setPreset}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {CLOUD_PRESETS[stageType].map((p) => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">
              The API key is stored in your OS credential manager, never in a plain settings file.
            </p>
          </TabsContent>

          <TabsContent value="localapi" className="flex flex-col gap-3 pt-2">
            <Input placeholder="Display name" value={name} onChange={(e) => setName(e.target.value)} />
            <div className="flex gap-2">
              <Input
                placeholder="Base URL (e.g. http://localhost:11434)"
                value={apiUrl}
                onChange={(e) => { setApiUrl(e.target.value); setDetection(null) }}
                onBlur={runDetection}
              />
              <Button type="button" variant="outline" size="sm" onClick={runDetection} disabled={detecting || !apiUrl.trim()}>
                {detecting ? "…" : "Detect"}
              </Button>
            </div>
          </TabsContent>
        </Tabs>

        {source === "cloud" && preset.startsWith("elevenlabs_") && (
          <Input aria-label="Quick Add service voice ID" placeholder="ElevenLabs voice ID"
            value={serviceVoiceId} onChange={(event) => setServiceVoiceId(event.target.value)} />
        )}
        {source !== "local" && (
          <details className="text-xs">
            <summary>Advanced service configuration</summary>
            <Textarea aria-label="Quick Add service configuration" value={serviceConfig}
              onChange={(event) => setServiceConfig(event.target.value)} className="mt-2 font-mono" />
          </details>
        )}

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Detected Stage</span>
            {detection && (
              <span className="text-[11px] text-muted-foreground">
                {detection.confidence === "high" ? "High confidence" : "Guess - please confirm"}
              </span>
            )}
          </div>
          <Select value={stageType} onValueChange={(v) => setStageType(v as StageType)}>
            <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STAGE_TABS.map((t) => (
                <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {detection?.reason && <p className="text-[11px] text-muted-foreground">{detection.reason}</p>}
        </div>

        <Button onClick={submit} disabled={busy}>{busy ? "Adding…" : "Add Model"}</Button>
        {error && <p className="text-xs text-destructive">{error}</p>}
      </DialogContent>
    </Dialog>
  )
}

function InstructionsEditor({ model, mp }: { model: ModelEntry; mp: ReturnType<typeof useMarketplace> }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(model.custom_instructions ?? "")
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function save() {
    setSaving(true)
    await mp.setInstructions(model.id, text)
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-left text-[11px] text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
      >
        {model.custom_instructions
          ? `Instructions: "${model.custom_instructions}"`
          : "+ Add custom instructions"}
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] text-muted-foreground">
        Extra instructions for this model (e.g. "avoid profanity, keep it formal") - appended to its prompt.
      </span>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Optional…"
        className="min-h-14 text-xs"
      />
      <div className="flex items-center gap-2">
        <Button size="sm" variant="secondary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Close</Button>
        {saved && <span className="text-[11px] text-success">Saved</span>}
      </div>
    </div>
  )
}

function ModelCard({ model, isActive, mp }: { model: ModelEntry; isActive: boolean; mp: ReturnType<typeof useMarketplace> }) {
  const { icon: KindIcon, label: kindLabel } = kindBadge(model.kind)
  const dl = mp.progress[model.id]

  return (
    <Card className={isActive ? "border-primary/60 bg-card" : "border-border bg-card"}>
      <CardContent className="flex flex-col gap-2 pt-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">{model.display_name}</span>
            <div className="flex items-center gap-1.5">
              <Badge variant="outline" className="gap-1"><KindIcon className="h-3 w-3" /> {kindLabel}</Badge>
              {model.status === "error" && <Badge variant="destructive">Error</Badge>}
              {model.status === "downloading" && <Badge variant="secondary">{model.meta?.cancel_requested ? "Stopping" : "Downloading"}</Badge>}
              {isActive && <Badge>Active</Badge>}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {model.status === 'downloading' && <Button size="sm" variant="outline"
              disabled={Boolean(model.meta?.cancel_requested)} onClick={() => mp.cancel(model.id)}>
              {model.meta?.cancel_requested ? 'Stopping…' : 'Stop download'}
            </Button>}
            <Button
              size="sm"
              variant={isActive ? "default" : "outline"}
              disabled={isActive || model.status !== "installed"}
              onClick={() => mp.setActive(model.id)}
              title="Set as active for this stage"
            >
              <Star className="h-3.5 w-3.5" />
            </Button>
            <Button size="sm" variant="ghost" onClick={() => mp.remove(model.id)} title="Remove">
              <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          </div>
        </div>

        {model.status === "downloading" && dl && (
          <div className="flex flex-col gap-1">
            <Progress value={dl.percent ?? 0} />
            <div className="flex justify-between text-[11px] text-muted-foreground">
              <span>{formatSpeed(dl.speed_bps)}</span>
              <span>{dl.percent != null ? `${dl.percent.toFixed(0)}%` : ""} {formatEta(dl.eta_seconds)}</span>
              {dl.progress_basis && <span>Transferring files; progress updates when each file finishes.</span>}
            </div>
          </div>
        )}

        {model.kind === "cloud_api" && (
          <span className="truncate text-[11px] text-muted-foreground">{model.api_base_url}</span>
        )}
        {model.request_preset === 'indicf5' && <p className="text-xs text-muted-foreground">Hindi only · Confirmed reference · {model.meta.speech_device === 'cuda:0' ? 'NVIDIA GPU for speech' : 'CPU for speech'}</p>}

        {INSTRUCTABLE_STAGES.includes(model.stage_type) && model.request_preset !== 'indictrans2' && <InstructionsEditor model={model} mp={mp} />}
      </CardContent>
    </Card>
  )
}

// Curated suggestions (core/recommended_models.py) - never installed on
// their own. "Download"/"Connect" opens the same Add Model dialog used
// everywhere else, prefilled, so the user still confirms (and, for cloud
// entries, still supplies their own API key) before anything is added.
function RecommendedSection({ stageType, onPick }: { stageType: StageType; onPick: (rec: RecommendedModel) => void }) {
  const [items, setItems] = useState<RecommendedModel[]>([])

  useEffect(() => {
    let cancelled = false
    bridge.listRecommendedModels(stageType).then((r) => { if (!cancelled) setItems(r) })
    return () => { cancelled = true }
  }, [stageType])

  if (items.length === 0) return null

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium text-muted-foreground">Recommended</span>
      <div className="grid grid-cols-1 items-stretch gap-2 md:grid-cols-2 xl:grid-cols-3">
        {items.map((rec) => (
          <div key={rec.name} className="flex h-full flex-col gap-1.5 rounded-md border border-dashed border-border p-3">
            <span className="text-sm font-medium">{rec.name}</span>
            <div className="flex flex-wrap items-center gap-1">
              {rec.best && (
                <Badge className="gap-1 border-transparent bg-amber-500 text-white" title="Our top pick for this stage">
                  <Star className="h-3 w-3 fill-current" /> Best
                </Badge>
              )}
              {rec.best_for_device && (
                <Badge className="gap-1" title="Fits your detected hardware">
                  <Cpu className="h-3 w-3" /> Best For This Device
                </Badge>
              )}
              {rec.tag && <Badge variant="outline">{rec.tag}</Badge>}
            </div>
            <p className="line-clamp-3 text-[11px] text-muted-foreground">{rec.note}</p>
            <div className="mt-auto pt-1">
              {rec.kind === "reference" ? (
                <a
                  href={rec.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-primary underline underline-offset-2"
                >
                  View project ↗
                </a>
              ) : (
                <Button size="sm" variant="secondary" onClick={() => onPick(rec)}>
                  {rec.kind === "local_file" ? "Download" : "Connect"}
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function HindiVoiceSetup({ refresh }: { refresh: () => Promise<void> }) {
  const [library, setLibrary] = useState<HindiVoiceLibrary | null>(null)
  const [selected, setSelected] = useState('')
  const [device, setDevice] = useState('cpu')
  const [audio, setAudio] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const voice = library?.profiles.find(item => item.id === selected)

  useEffect(() => {
    let cancelled = false
    bridge.listHindiVoices().then(result => {
      if (cancelled) return
      setLibrary(result); setSelected(result.profiles[0]?.id ?? '')
      setDevice(result.devices[0] ?? 'cpu')
    }).catch(error => { if (!cancelled) setMessage(String(error)) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    setAudio(null); setConfirmed(false); setMessage('')
    if (selected) bridge.previewHindiVoice(selected).then(result => {
      if (cancelled) return
      if (result.ok && result.audio) setAudio(result.audio)
      else setMessage(result.message ?? 'Reference preview unavailable.')
    }).catch(error => { if (!cancelled) setMessage(String(error)) })
    return () => { cancelled = true }
  }, [selected])

  async function connect() {
    setBusy(true); setMessage('')
    try {
      const result = await bridge.connectHindiVoice(selected, device, confirmed)
      setMessage(result.ok ? 'Connected. Select this voice with the star below, then choose Hindi. Its confirmed reference recording will be used automatically.' : result.message ?? 'Could not connect the voice.')
      if (result.ok) await refresh()
    } catch (error) { setMessage(String(error)) }
    finally { setBusy(false) }
  }

  return <Card><CardContent className="flex flex-col gap-3 pt-4">
    <span className="text-sm font-medium">Hindi voices</span>
    <p className="text-xs text-muted-foreground">Connect a confirmed voice already on this computer. Listen to the reference and check its words before using it.</p>
    {voice && <>
      <Select value={selected} onValueChange={setSelected} disabled={busy}>
        <SelectTrigger aria-label="Hindi voice"><SelectValue /></SelectTrigger>
        <SelectContent>{library?.profiles.map(item => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}</SelectContent>
      </Select>
      <p className="text-sm" lang="hi">{voice.text}</p>
      {audio && <CueAudioPlayer audio={audio} />}
      <p className="break-all text-xs text-muted-foreground">Reference audio: {voice.reference_audio}</p>
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={confirmed} disabled={!audio || busy} onChange={event => setConfirmed(event.target.checked)} />I listened and these words match the reference.</label>
      <Select value={device} onValueChange={setDevice} disabled={busy}>
        <SelectTrigger aria-label="Hindi speech processor"><SelectValue /></SelectTrigger>
        <SelectContent>{library?.devices.map(item => <SelectItem key={item} value={item}>{item === 'cpu' ? 'CPU (slower)' : 'NVIDIA GPU (Hindi speech)'}</SelectItem>)}</SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">This processor choice applies to Hindi speech. Other stages use the workspace processor. Hindi output and this confirmed voice are required.</p>
      <Button onClick={connect} disabled={busy || !confirmed || !library?.model_ready || !library?.devices.includes(device)}>{busy ? 'Connecting…' : 'Connect Hindi voice'}</Button>
    </>}
    {library && !voice && <p className="text-xs">No confirmed Hindi reference is available yet.</p>}
    {library && !library.model_ready && <p role="alert" className="text-xs">{library.message}</p>}
    {message && <p role="status" className="text-xs">{message}</p>}
  </CardContent></Card>
}

function StrongRecognitionSetup({ refresh }: { refresh: () => Promise<void> }) {
  const [status, setStatus] = useState<{ ready: boolean; message: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  useEffect(() => { bridge.whisperTurboStatus().then(setStatus).catch(() => setMessage('Could not check the installed recognizer.')) }, [])
  async function connect() {
    setBusy(true)
    try {
      const result = await bridge.connectWhisperTurbo()
      setMessage(result.ok ? 'Connected. Choose Set Active on its card to use it.' : result.message ?? 'Connection failed.')
      if (result.ok) await refresh()
    } catch { setMessage('Could not connect the installed recognizer.') }
    finally { setBusy(false) }
  }
  return <Card><CardContent className="flex flex-col gap-2 p-4">
    <h3 className="text-sm font-semibold">Stronger speech recognition</h3>
    <p className="text-xs text-muted-foreground">Use the installed Whisper model to improve the words passed to translation. It uses your NVIDIA GPU, then releases it before translation and speech generation.</p>
    <p className="text-xs text-muted-foreground">Review the recognised words before dubbing. Language confidence does not guarantee correct wording. Connecting preserves your current active selection.</p>
    {status && <p className="text-xs">{status.message}</p>}
    <Button disabled={busy || !status?.ready} onClick={connect}>{busy ? 'Connecting…' : 'Connect installed Whisper'}</Button>
    {message && <p role="status" className="text-xs">{message}</p>}
  </CardContent></Card>
}

function HindiTranslationSetup({ refresh }: { refresh: () => Promise<void> }) {
  const [status, setStatus] = useState<{ ready: boolean; message: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  useEffect(() => { bridge.indicTrans2Status().then(setStatus).catch(() => setMessage('Could not check the installed translation engine.')) }, [])
  async function connect() {
    setBusy(true)
    try {
      const result = await bridge.connectIndicTrans2()
      setMessage(result.ok ? 'Connected. Choose Set Active on its card when you want to use it.' : result.message ?? 'Connection failed.')
      if (result.ok) await refresh()
    } catch { setMessage('Could not connect the installed translation engine.') }
    finally { setBusy(false) }
  }
  return <Card><CardContent className="flex flex-col gap-2 p-4">
    <h3 className="text-sm font-semibold">Hindi translation</h3>
    <p className="text-xs text-muted-foreground">IndicTrans2 translates English text into Hindi. It uses your NVIDIA GPU, then releases it before speech generation. Use NLLB for other source or output languages.</p>
    <p className="text-xs text-muted-foreground">Use cue review to check wording and shorten lines that do not fit. Connecting adds the installed model; it does not change your active selection.</p>
    {status && <p className="text-xs">{status.message}</p>}
    <Button disabled={busy || !status?.ready} onClick={connect}>{busy ? 'Connecting…' : 'Connect installed IndicTrans2'}</Button>
    {message && <p role="status" className="text-xs">{message}</p>}
  </CardContent></Card>
}

function StageTabContent({ stageType }: { stageType: StageType }) {
  const mp = useMarketplace(stageType)
  const [recDialogOpen, setRecDialogOpen] = useState(false)
  const [recPrefill, setRecPrefill] = useState<AddModelPrefill | null>(null)

  function handleRecommendedPick(rec: RecommendedModel) {
    if (rec.kind === "local_file") {
      setRecPrefill({ tab: "local", name: rec.name, url: rec.source_url ?? "", preset: rec.request_preset })
    } else if (rec.kind === "cloud_api") {
      setRecPrefill({ tab: "cloud", name: rec.name, url: rec.api_base_url ?? "", preset: rec.request_preset })
    } else {
      return
    }
    setRecDialogOpen(true)
  }

  return (
    <div className="flex flex-col gap-3">
      {stageType === 'tts' && <HindiVoiceSetup refresh={mp.refresh} />}
      {stageType === 'stt' && <StrongRecognitionSetup refresh={mp.refresh} />}
      {stageType === 'translation' && <HindiTranslationSetup refresh={mp.refresh} />}
      <RecommendedSection stageType={stageType} onPick={handleRecommendedPick} />
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {mp.models.length} model{mp.models.length === 1 ? "" : "s"}
        </span>
        <AddModelDialog stageType={stageType} mp={mp} />
        <AddModelDialog
          stageType={stageType}
          mp={mp}
          open={recDialogOpen}
          onOpenChange={setRecDialogOpen}
          hideTrigger
          prefill={recPrefill}
        />
      </div>
      {mp.models.length === 0 ? (
        <div className="rounded-md border border-dashed border-border py-8 text-center text-xs text-muted-foreground">
          No models connected for this stage yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {mp.models.map((m) => (
            <ModelCard key={m.id} model={m} isActive={m.id === mp.activeId} mp={mp} />
          ))}
        </div>
      )}
    </div>
  )
}

export function MarketplacePage() {
  const [autoDetectEnabled, setAutoDetectEnabled] = useState(false)
  const [activeStageTab, setActiveStageTab] = useState<StageType>("voice")

  useEffect(() => {
    bridge.getSettings().then(({ values }) => setAutoDetectEnabled(values.auto_detect_model_type))
  }, [])

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold" style={{ fontFamily: "var(--font-display)" }}>MARKETPLACE</h1>
          <p className="text-xs text-muted-foreground">
            Connect local downloads, cloud APIs, or local services for every stage of the pipeline.
          </p>
        </div>
        {autoDetectEnabled && <QuickAddDialog />}
      </div>

      <Tabs value={activeStageTab} onValueChange={(v) => setActiveStageTab(v as StageType)}>
        <TabsList className="grid w-full grid-cols-4 gap-1 lg:grid-cols-8">
          {STAGE_TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id} className="text-[11px] sm:text-xs">{t.label}</TabsTrigger>
          ))}
        </TabsList>
        {STAGE_TABS.map((t) => (
          <TabsContent key={t.id} value={t.id} className="pt-4">
            <StageTabContent stageType={t.id} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
