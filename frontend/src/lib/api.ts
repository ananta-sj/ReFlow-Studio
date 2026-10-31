// Typed wrapper around window.pywebview.api.* - the bridge/api.py surface.
// Waits for the `pywebviewready` event since pywebview injects
// window.pywebview asynchronously after the page's own load.

export interface DeletionResult {
  ok: boolean
  message?: string
  removed?: string[]
  remaining?: string[]
  retained?: { path: string; reason: string }[]
}

export interface QueueJob {
  id: string
  input_path: string
  params: Partial<RenderParams> | null
  template_id: PipelineTemplateId
  status: 'draft' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  status_text: string
  output_path: string | null
  error: string | null
  created_at: number
}

export interface JobActionResult { ok: boolean; message?: string }

export interface SessionSnapshot {
  sessionId: string
  revision: number
  render: import('./render-state').RenderState
  queue: QueueJob[]
  busy: boolean
  paused: boolean
  lastEventAt: number
}

export interface DeletionPreview extends DeletionResult {
  token?: string
  candidates?: { path: string; files: number; bytes: number }[]
  files?: number
  bytes?: number
}

export interface DeviceInfo {
  id: string
  label: string
  kind: "dedicated" | "integrated" | "cpu"
  backend: string
}

export interface HardwareSnapshot {
  cpu_name: string
  cpu_percent: number
  ram_used_gb: number
  ram_total_gb: number
  vram_used_mb: number | null
  vram_total_mb: number | null
  gpu_name: string
  gpu_kind: string
  default_device_id: string
  devices: DeviceInfo[]
}

export interface JobEstimate {
  eta_seconds: number
  peak_vram_mb: number | null
  peak_vram_by_device_mb?: Record<string, number | null>
  audio_buffer_ram_mb?: number
  segment_buffer_window?: number
  speech_components?: { role: string; id: string; device: string; cost_ratio: number; model_memory_mb: number }[]
  estimate_basis?: string
  warnings?: string[]
  stage_devices?: Record<string, string>
}

export type DeviceEtaMap = Record<string, JobEstimate>

export type StageType = "stt" | "translation" | "tts" | "voice" | "enhancer" | "filter" | "lipsync" | "profanity_filter"
export type ModelKind = "local_file" | "local_api" | "cloud_api"
export type ModelStatus = "installed" | "downloading" | "error" | "not_downloaded"

export interface ModelEntry {
  id: string
  stage_type: StageType
  kind: ModelKind
  display_name: string
  source_url: string | null
  local_path: string | null
  api_base_url: string | null
  credential_ref: string | null
  request_preset: string | null
  status: ModelStatus
  meta: Record<string, unknown>
  custom_instructions: string | null
}

export type ActiveModelMap = Record<StageType, ModelEntry | null>

export interface HindiVoiceLibrary {
  profiles: { id: string; name: string; text: string; reference_audio: string }[]
  devices: string[]
  model_ready: boolean
  message: string
}

export interface RecommendedModel {
  name: string
  kind: "local_file" | "cloud_api" | "reference"
  source_url?: string
  api_base_url?: string
  request_preset?: string
  note: string
  tag?: string
  approx_vram_gb?: number
  best_for_device: boolean
  best?: boolean
}

export interface Language {
  code: string
  name: string
}

export interface HardwareProfile {
  cpu_name: string
  ram_total_gb: number | null
  best_device: { id: string; kind: string; name: string; vram_total_mb: number | null }
}

export type RecommendedModelMap = Partial<Record<StageType, RecommendedModel[]>>

export interface ModelActionResult {
  ok: boolean
  message?: string
  model?: ModelEntry
}

export interface ModelDownloadProgress {
  modelId: string
  phase: "downloading" | "done"
  downloaded: number
  total: number | null
  percent: number | null
  speed_bps: number
  eta_seconds: number | null
  progress_basis?: string
}

export interface NodeParamDef {
  key: string
  kind: "combo" | "checkbox" | "readonly"
  label: string
  default: unknown
  options: [string, string][]
}

export interface GraphNodeDef {
  id: string
  title: string
  icon: string
  mutable: boolean
  duplicable: boolean
  removable: boolean
  headerColor: string | null
  x: number
  y: number
  enabled: boolean
  params: NodeParamDef[]
}

export interface GraphEdgeDef {
  source: string
  target: string
}

export interface GraphDefinition {
  nodes: GraphNodeDef[]
  edges: GraphEdgeDef[]
}

export interface RenderParams {
  voice: string
  lang: string
  source_language?: string
  ref_audio: string | null
  keep_bg: boolean
  lipsync: boolean
  enhance: boolean
  burn_subs: boolean
  content_filter: boolean
  task_priority: number
  texture_quality: number
  device_id: string
  parallel_workers: number
  include_subtitles?: boolean
  export_stems?: boolean
  sub_style?: { font_size: number }
}

export interface SourceLanguageFeedback {
  source_code: string | null
  source_name: string | null
  origin: "manual" | "detected" | "unknown"
  resolved: boolean
  detected_language: string | null
  detected_name: string | null
  probability: number | null
  minimum_confidence: number
}

export interface ReviewTake { seconds: number; fits: boolean }
export interface ReviewCue {
  dialogue_supervision?: {
    meaning_review_protocol?: 'quoted-spans.v1' | 'legacy-reasons.v1'
    status: string; outcome: string; writer_requests: number; reviewer_requests: number
    candidates: { id: string; text: string; predicted_seconds: number | null; fits: boolean | null; warnings: string[]
      meaning_status: 'not_reviewed' | 'preserved' | 'changed' | 'uncertain'; meaning_reasons: string[];
      meaning_evidence?: { source_quote: string; candidate_quote: string; relation: 'equivalent' | 'changed' | 'omitted' | 'added' | 'uncertain' }[]; approved: false }[]
  }
  dialogue_options?: { status: string; available_seconds: number; candidates: { text: string; predicted_seconds: number; fits: boolean; warnings: string[]; approved: false }[] }
  cue_id?: string
  start: number; end: number; available_seconds: number
  source_text: string; text: string
  candidate: ReviewTake | null; accepted: ReviewTake | null
}
export interface CueReview {
  output_kind?: 'audio' | 'video'
  id: string; name: string; revision: number; duration: number; target_lang: string
  cues: ReviewCue[]
}
export interface CueTimingResult {
  ok: boolean
  supported?: boolean
  estimated_seconds?: number
  available_seconds?: number
  fits?: boolean
  message?: string
}

export interface CueReviewResult {
  ok: boolean; message?: string; review?: CueReview; audio?: string
}
export interface CueReviewListResult {
  ok: boolean; message?: string; reviews: { id: string; name: string; created_at: number }[]
}

export type PipelineTemplateId = "video_dub" | "video_dub_lipsync" | "audio_dub" | "subtitle_translate"

export interface InterruptedRender {
  recovery_token: string
  input_path: string
  params: Partial<RenderParams>
  template_id: PipelineTemplateId
  started_at: number
}

export interface PipelineTemplate {
  label: string
  input_kind: "video" | "audio" | "subtitle"
}

export type PipelineTemplateMap = Record<PipelineTemplateId, PipelineTemplate>

export interface AppSettings {
  default_language: string
  default_voice: string
  default_task_priority: number
  default_texture_quality: number
  keep_bg_default: boolean
  content_filter_default: boolean
  auto_cleanup_temp: boolean
  ollama_host: string
  whisper_model_size: string
  xtts_runtime: 'legacy' | 'isolated'
  recognition_runtime?: 'legacy' | 'isolated'
  nllb_runtime?: 'legacy' | 'isolated'
  m2m100_runtime?: 'legacy' | 'isolated'
  separation_runtime?: 'legacy' | 'isolated'
  enhancement_runtime?: 'legacy' | 'isolated'
  auto_detect_model_type: boolean
  search_provider: string
  search_engine_id: string
  onboarding_complete: boolean
  dialogue_mode: 'off' | 'local' | 'hybrid'
  dialogue_writer_id: string
  dialogue_reviewer_id: string
  dialogue_text_consent: boolean
  dialogue_consent_fingerprint: string
}

export interface ModelTypeDetection {
  stage_type: StageType | null
  confidence: "high" | "low"
  reason: string
}

export interface HfModelPick {
  repo_id: string
  url: string
  downloads: number
  likes: number
}

export interface WebSearchResult {
  title: string
  link: string
  snippet: string
}

export interface BestModelResult {
  hf_picks: HfModelPick[]
  web_results: WebSearchResult[]
}

export interface SearchConfig {
  provider: string
  engine_id: string
  configured: boolean
}

export interface SettingsResponse {
  values: AppSettings
  whisper_model_sizes: string[]
  xtts_runtime_status?: string
  recognition_runtime_status?: string
  nllb_runtime_status?: string
  m2m100_runtime_status?: string
  separation_runtime_status?: string
  enhancement_runtime_status?: string
}

export interface EngineReadiness {
  status: "needs_setup" | "inspection_complete"
  explanation: string
  warnings: string[]
  checks: { stage: string; label: string; status: "checked" | "unverified" | "needs_setup"; model?: string; details: string[]; guidance?: string;
    runtime?: { status: "passed" | "failed" | "unverified"; versions?: Record<string, string>; device_name?: string } }[]
}

export interface DialogueReadiness {
  status: string; ready: boolean; message: string
  writer?: { label: string; model: string; endpoint: string; local: boolean }
  reviewer?: { label: string; model: string; endpoint: string; local: boolean }
}

declare global {
  interface Window {
    pywebview: {
      api: {
        get_hardware_snapshot: (deviceId?: string | null) => Promise<HardwareSnapshot>
        capture_hardware_profile: () => Promise<HardwareProfile>
        estimate_job: (
          videoPath: string,
          stageFlags: Partial<RenderParams>,
          deviceId: string
        ) => Promise<JobEstimate>
        estimate_job_all_devices: (videoPath: string, stageFlags: Partial<RenderParams>) => Promise<DeviceEtaMap>
        list_models: (stageType?: StageType | null) => Promise<ModelEntry[]>
        list_recommended_models: (stageType?: StageType | null) => Promise<RecommendedModel[] | RecommendedModelMap>
        get_active_models: () => Promise<ActiveModelMap>
        list_hindi_voices: () => Promise<HindiVoiceLibrary>
        indictrans2_status: () => Promise<{ ready: boolean; message: string }>
        whisper_turbo_status: () => Promise<{ ready: boolean; message: string }>
        connect_whisper_turbo: () => Promise<ModelActionResult>
        connect_indictrans2: () => Promise<ModelActionResult>
        preview_hindi_voice: (identifier: string) => Promise<{ ok: boolean; audio?: string; message?: string }>
        connect_hindi_voice: (identifier: string, device: string, confirmed: boolean) => Promise<ModelActionResult>
        set_active_model: (stageType: StageType, modelId: string) => Promise<{ ok: boolean; message?: string }>
        set_model_instructions: (modelId: string, customInstructions: string) => Promise<{ ok: boolean; model?: ModelEntry }>
        preview_model_removal: (modelId: string) => Promise<DeletionPreview>
        preview_factory_reset: () => Promise<DeletionPreview>
        remove_model: (modelId: string, previewToken?: string) => Promise<DeletionResult>
        add_local_model: (
          stageType: StageType,
          sourceUrl: string,
          displayName: string,
          requestPreset?: string | null
        ) => Promise<ModelActionResult>
        add_cloud_model: (
          stageType: StageType,
          displayName: string,
          apiBaseUrl: string,
          apiKey: string,
          requestPreset: string,
          requestConfig?: Record<string, unknown>
        ) => Promise<ModelActionResult>
        add_local_api_model: (
          stageType: StageType,
          displayName: string,
          apiBaseUrl: string,
          requestPreset: string,
          requestConfig?: Record<string, unknown>
        ) => Promise<ModelActionResult>
        add_airllm_model: (displayName: string, hfModelId: string, compression: string) => Promise<ModelActionResult>
        browse_video: () => Promise<string[]>
        browse_audio: () => Promise<string | null>
        browse_subtitle: () => Promise<string | null>
        list_cue_reviews: () => Promise<CueReviewListResult>
        get_cue_review: (id: string) => Promise<CueReviewResult>
        edit_review_cue: (id: string, revision: number, index: number, sourceText: string, text: string, start?: number, end?: number) => Promise<CueReviewResult>
        combine_review_cues: (id: string, revision: number, index: number) => Promise<CueReviewResult>
        accept_review_cue: (id: string, revision: number, index: number) => Promise<CueReviewResult>
        estimate_review_timing: (id: string, revision: number, index: number) => Promise<CueTimingResult>
        get_review_audio: (id: string, index: number, accepted: boolean) => Promise<CueReviewResult>
        get_review_source_audio: (id: string, index: number) => Promise<CueReviewResult>
        start_cue_review: (path: string, params: Partial<RenderParams>) => Promise<JobActionResult>
        start_review_action: (id: string, revision: number, action: "generate" | "translate" | "adapt" | "supervise" | "render", index: number | null) => Promise<JobActionResult>
        detect_model_type: (link: string, linkKind: "url" | "api_base_url") => Promise<ModelTypeDetection>
        find_best_model: (stageType: StageType) => Promise<BestModelResult>
        get_search_config: () => Promise<SearchConfig>
        set_search_credentials: (provider: string, apiKey: string, engineId: string) => Promise<{ ok: boolean; message?: string }>
        list_pipeline_templates: () => Promise<PipelineTemplateMap>
        get_graph_definition: () => Promise<GraphDefinition>
        set_node_enabled: (nodeId: string, enabled: boolean) => Promise<{ ok: boolean; message?: string }>
        set_node_param: (nodeId: string, key: string, value: unknown) => Promise<{ ok: boolean; message?: string }>
        add_node_instance: (specId: string) => Promise<{ ok: boolean; nodeId?: string; message?: string }>
        remove_node_instance: (nodeId: string) => Promise<{ ok: boolean; message?: string }>
        set_node_position: (nodeId: string, x: number, y: number) => Promise<{ ok: boolean; message?: string }>
        run_integrity_check: () => Promise<{ ok: boolean; message: string }>
        factory_reset: (previewToken?: string) => Promise<DeletionResult>
        start_render: (
          inputPath: string,
          params: Partial<RenderParams>,
          templateId: PipelineTemplateId
        ) => Promise<{ ok: boolean; message?: string }>
        stop_render: () => Promise<{ ok: boolean; stopping: boolean }>
        get_interrupted_render: () => Promise<InterruptedRender | null>
        resume_interrupted_render: (recoveryToken: string) => Promise<{ ok: boolean; message?: string }>
        cancel_model_download: (modelId: string) => Promise<{ ok: boolean; message?: string }>
        discard_interrupted_render: (recoveryToken: string) => Promise<{ ok: boolean; message?: string }>
        get_session_state: () => Promise<SessionSnapshot>
        add_queue_drafts: (paths: string[]) => Promise<JobActionResult>
        start_queue_batch: (params: Partial<RenderParams>, templateId: PipelineTemplateId, expectedIds?: string[]) => Promise<JobActionResult>
        resume_queue_batch: () => Promise<JobActionResult>
        remove_queue_item: (itemId: string) => Promise<JobActionResult>
        clear_completed_queue: () => Promise<JobActionResult>
        set_queue_paused: (paused: boolean) => Promise<JobActionResult>
        minimize_window: () => Promise<void>
        minimize_to_tray: () => Promise<{ ok: boolean }>
        toggle_maximize_window: () => Promise<void>
        close_window: () => Promise<void>
        get_settings: () => Promise<SettingsResponse>
        get_ui_preferences: () => Promise<Record<string, string>>
        update_ui_preferences: (partial: Record<string, string>) => Promise<Record<string, string>>
        get_dialogue_readiness: () => Promise<DialogueReadiness>
        get_engine_readiness: (params: Partial<RenderParams>, templateId: PipelineTemplateId, verifyRuntime: boolean) => Promise<EngineReadiness>
        list_languages: () => Promise<Language[]>
        list_source_languages: () => Promise<Language[]>
        update_settings: (partial: Partial<AppSettings>) => Promise<AppSettings>
        reset_settings: () => Promise<AppSettings>
      }
    }
  }
}

let readyPromise: Promise<void> | null = null

export function whenReady(): Promise<void> {
  if (window.pywebview?.api) return Promise.resolve()
  if (!readyPromise) {
    readyPromise = new Promise((resolve) => {
      window.addEventListener("pywebviewready", () => resolve(), { once: true })
    })
  }
  return readyPromise
}

async function api() {
  await whenReady()
  return window.pywebview.api
}

export const bridge = {
  getUiPreferences: async (): Promise<Record<string, string>> => (await api()).get_ui_preferences(),
  updateUiPreferences: async (partial: Record<string, string>): Promise<Record<string, string>> => (await api()).update_ui_preferences(partial),
  getHardwareSnapshot: async (deviceId?: string) => (await api()).get_hardware_snapshot(deviceId),
  captureHardwareProfile: async () => (await api()).capture_hardware_profile(),
  estimateJob: async (videoPath: string, stageFlags: Partial<RenderParams>, deviceId: string) =>
    (await api()).estimate_job(videoPath, stageFlags, deviceId),
  estimateJobAllDevices: async (videoPath: string, stageFlags: Partial<RenderParams>) =>
    (await api()).estimate_job_all_devices(videoPath, stageFlags),
  listModels: async (stageType?: StageType) => (await api()).list_models(stageType),
  listRecommendedModels: async (stageType?: StageType) =>
    (await api()).list_recommended_models(stageType) as Promise<RecommendedModel[]>,
  getActiveModels: async () => (await api()).get_active_models(),
  listHindiVoices: async () => (await api()).list_hindi_voices(),
  indicTrans2Status: async () => (await api()).indictrans2_status(),
  whisperTurboStatus: async () => (await api()).whisper_turbo_status(),
  connectWhisperTurbo: async () => (await api()).connect_whisper_turbo(),
  connectIndicTrans2: async () => (await api()).connect_indictrans2(),
  previewHindiVoice: async (identifier: string) => (await api()).preview_hindi_voice(identifier),
  connectHindiVoice: async (identifier: string, device: string, confirmed: boolean) =>
    (await api()).connect_hindi_voice(identifier, device, confirmed),
  setActiveModel: async (stageType: StageType, modelId: string) => (await api()).set_active_model(stageType, modelId),
  setModelInstructions: async (modelId: string, customInstructions: string) =>
    (await api()).set_model_instructions(modelId, customInstructions),
  previewModelRemoval: async (modelId: string) => (await api()).preview_model_removal(modelId),
  previewFactoryReset: async () => (await api()).preview_factory_reset(),
  removeModel: async (modelId: string, previewToken?: string) => (await api()).remove_model(modelId, previewToken),
  addLocalModel: async (stageType: StageType, sourceUrl: string, displayName: string, requestPreset?: string | null) =>
    (await api()).add_local_model(stageType, sourceUrl, displayName, requestPreset),
  addCloudModel: async (
    stageType: StageType,
    displayName: string,
    apiBaseUrl: string,
    apiKey: string,
    requestPreset: string,
    requestConfig?: Record<string, unknown>
  ) => (await api()).add_cloud_model(stageType, displayName, apiBaseUrl, apiKey, requestPreset, requestConfig),
  addLocalApiModel: async (
    stageType: StageType,
    displayName: string,
    apiBaseUrl: string,
    requestPreset: string,
    requestConfig?: Record<string, unknown>
  ) => (await api()).add_local_api_model(stageType, displayName, apiBaseUrl, requestPreset, requestConfig),
  addAirllmModel: async (displayName: string, hfModelId: string, compression: string) =>
    (await api()).add_airllm_model(displayName, hfModelId, compression),
  browseVideo: async () => (await api()).browse_video(),
  browseAudio: async () => (await api()).browse_audio(),
  browseSubtitle: async () => (await api()).browse_subtitle(),
  listCueReviews: async () => (await api()).list_cue_reviews(),
  getCueReview: async (id: string) => (await api()).get_cue_review(id),
  editReviewCue: async (id: string, revision: number, index: number, sourceText: string, text: string, start?: number, end?: number) => (await api()).edit_review_cue(id, revision, index, sourceText, text, start, end),
  combineReviewCues: async (id: string, revision: number, index: number) => (await api()).combine_review_cues(id, revision, index),
  acceptReviewCue: async (id: string, revision: number, index: number) => (await api()).accept_review_cue(id, revision, index),
  estimateReviewTiming: async (id: string, revision: number, index: number) => (await api()).estimate_review_timing(id, revision, index),
  getReviewAudio: async (id: string, index: number, accepted = false) => (await api()).get_review_audio(id, index, accepted),
  getReviewSourceAudio: async (id: string, index: number) => (await api()).get_review_source_audio(id, index),
  startCueReview: async (path: string, params: Partial<RenderParams>) => (await api()).start_cue_review(path, params),
  startReviewAction: async (id: string, revision: number, action: "generate" | "translate" | "adapt" | "supervise" | "render", index: number | null = null) => (await api()).start_review_action(id, revision, action, index),
  detectModelType: async (link: string, linkKind: "url" | "api_base_url" = "url") =>
    (await api()).detect_model_type(link, linkKind),
  findBestModel: async (stageType: StageType) => (await api()).find_best_model(stageType),
  getSearchConfig: async () => (await api()).get_search_config(),
  setSearchCredentials: async (provider: string, apiKey: string, engineId: string) =>
    (await api()).set_search_credentials(provider, apiKey, engineId),
  listPipelineTemplates: async () => (await api()).list_pipeline_templates(),
  getGraphDefinition: async () => (await api()).get_graph_definition(),
  setNodeEnabled: async (nodeId: string, enabled: boolean) => (await api()).set_node_enabled(nodeId, enabled),
  setNodeParam: async (nodeId: string, key: string, value: unknown) => (await api()).set_node_param(nodeId, key, value),
  addNodeInstance: async (specId: string) => (await api()).add_node_instance(specId),
  removeNodeInstance: async (nodeId: string) => (await api()).remove_node_instance(nodeId),
  setNodePosition: async (nodeId: string, x: number, y: number) => (await api()).set_node_position(nodeId, x, y),
  runIntegrityCheck: async () => (await api()).run_integrity_check(),
  factoryReset: async (previewToken?: string) => (await api()).factory_reset(previewToken),
  startRender: async (inputPath: string, params: Partial<RenderParams>, templateId: PipelineTemplateId = "video_dub") =>
    (await api()).start_render(inputPath, params, templateId),
  stopRender: async () => (await api()).stop_render(),
  getInterruptedRender: async () => (await api()).get_interrupted_render(),
  resumeInterruptedRender: async (recoveryToken: string) => (await api()).resume_interrupted_render(recoveryToken),
  cancelModelDownload: async (modelId: string) => (await api()).cancel_model_download(modelId),
  discardInterruptedRender: async (recoveryToken: string) => (await api()).discard_interrupted_render(recoveryToken),
  getSessionState: async () => (await api()).get_session_state(),
  addQueueDrafts: async (paths: string[]) => (await api()).add_queue_drafts(paths),
  startQueueBatch: async (params: Partial<RenderParams>, templateId: PipelineTemplateId, expectedIds?: string[]) => (await api()).start_queue_batch(params, templateId, expectedIds),
  resumeQueueBatch: async () => (await api()).resume_queue_batch(),
  removeQueueItem: async (itemId: string) => (await api()).remove_queue_item(itemId),
  clearCompletedQueue: async () => (await api()).clear_completed_queue(),
  setQueuePaused: async (paused: boolean) => (await api()).set_queue_paused(paused),
  minimizeWindow: async () => (await api()).minimize_window(),
  minimizeToTray: async () => (await api()).minimize_to_tray(),
  toggleMaximizeWindow: async () => (await api()).toggle_maximize_window(),
  closeWindow: async () => {
    const { flushPreferences } = await import('./preference-storage')
    await flushPreferences()
    return (await api()).close_window()
  },
  getSettings: async () => (await api()).get_settings(),
  getDialogueReadiness: async () => (await api()).get_dialogue_readiness(),
  getEngineReadiness: async (params: Partial<RenderParams>, templateId: PipelineTemplateId, verifyRuntime = false) => (await api()).get_engine_readiness(params, templateId, verifyRuntime),
  listLanguages: async () => (await api()).list_languages(),
  listSourceLanguages: async () => (await api()).list_source_languages(),
  updateSettings: async (partial: Partial<AppSettings>) => (await api()).update_settings(partial),
  resetSettings: async () => (await api()).reset_settings(),
}
