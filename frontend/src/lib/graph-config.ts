import type { GraphNodeDef, Language } from './api'
import type { RenderConfig } from './use-render-config'

export function isVoiceNode(id: string) { return /^tts_rvc(?:_\d+)?$/.test(id) }

export function projectGraphNode(node: GraphNodeDef, cfg: RenderConfig, voiceCount: number,
  languages: Language[], inputPath: string | null,
  stageMap: Record<string, keyof RenderConfig> = {}): GraphNodeDef {
  const language = cfg.lang === 'source' ? 'Source language (no translation)'
    : `${languages.find(item => item.code === cfg.lang)?.name ?? cfg.lang} (${cfg.lang})`
  const enabled = cfg[stageMap[node.id]]
  return { ...node, enabled: typeof enabled === 'boolean' ? enabled : node.enabled,
    params: node.params.map(param => {
    const value = node.id === 'translate' && param.key === 'lang' ? language
      : node.id === 'input' && param.key === 'video_name' ? inputPath?.split(/[\\/]/).pop() ?? ''
      : isVoiceNode(node.id) && voiceCount === 1 && param.key === 'voice' ? cfg.voice : param.default
    return { ...param, default: value }
  }) }
}
