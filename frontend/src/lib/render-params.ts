import type { RenderParams } from "@/lib/api"
import { QUALITY_STEPS, type RenderConfig } from "@/lib/use-render-config"

export function buildRenderParams(cfg: RenderConfig, deviceId: string, inputKind: "video" | "audio" | "subtitle", templateId = cfg.template): Partial<RenderParams> {
  const language = { lang: cfg.lang, source_language: cfg.sourceLanguage }
  if (inputKind === "subtitle") return language
  const audio = { ...language, voice: cfg.voice, ref_audio: cfg.refAudio, keep_bg: cfg.keepBg,
    device_id: deviceId, parallel_workers: cfg.parallelWorkers, export_stems: cfg.exportStems }
  if (inputKind === "audio") return audio
  return { ...audio, lipsync: templateId === "video_dub_lipsync" || cfg.lipsync, enhance: cfg.enhance, burn_subs: cfg.includeSubtitles && cfg.burnSubs, include_subtitles: cfg.includeSubtitles,
    sub_style: cfg.includeSubtitles && cfg.burnSubs ? { font_size: cfg.subtitleFontSize } : undefined,
    content_filter: cfg.contentFilter, task_priority: cfg.taskPriority,
    texture_quality: QUALITY_STEPS[cfg.qualityIdx] }
}
