import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'

const read = path => fs.readFileSync(new URL('../' + path, import.meta.url), 'utf8')
const config = read('src/lib/use-render-config.ts')
const quality = config.match(/export const QUALITY_STEPS = (\[[^\]]+\])/)[1]
const source = read('src/lib/render-params.ts').replace(
  /import \{ QUALITY_STEPS, type RenderConfig \} from "@\/lib\/use-render-config"/,
  'type RenderConfig = any; const QUALITY_STEPS = ' + quality)
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { buildRenderParams } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
let checks = 0
function check(value, label) { assert.ok(value, label); checks++; console.log('PASS ' + label) }
const cfg = { lang: 'en', sourceLanguage: 'fr', voice: 'unique-voice-id', refAudio: 'reference.wav',
  keepBg: true, parallelWorkers: 3, lipsync: true, enhance: true, burnSubs: true,
  contentFilter: true, taskPriority: 75, qualityIdx: 2, includeSubtitles: false,
  exportStems: true, subtitleFontSize: 40 }
const video = buildRenderParams(cfg, 'cpu', 'video')
check(video.source_language === 'fr', 'video preserves source language')
check(video.voice === 'unique-voice-id', 'video preserves unique voice connection')
check(video.include_subtitles === false && video.burn_subs === false, 'muted subtitles also disable burn-in')
check(video.sub_style === undefined, 'muted subtitles omit styling')
check(video.export_stems === true, 'video stem export reaches backend')
check(video.texture_quality === 4 && video.parallel_workers === 3, 'quality and workers reach backend')
const styled = buildRenderParams({ ...cfg, includeSubtitles: true }, 'cpu', 'video')
check(styled.sub_style.font_size === 40 && styled.burn_subs, 'enabled burn-in preserves chosen font size')
const audio = buildRenderParams(cfg, 'cpu', 'audio')
check(audio.export_stems === true, 'audio stem export reaches backend')
check(!('sub_style' in audio) && !('include_subtitles' in audio), 'audio parameters omit unsupported subtitle features')
const subtitle = buildRenderParams(cfg, 'cpu', 'subtitle')
check(Object.keys(subtitle).length === 2 && subtitle.source_language === 'fr', 'subtitle jobs retain only language settings')
check(read('src/pages/Nodes.tsx').includes('const params = buildRenderParams(cfg, selectedDeviceId, "video", cfg.lipsync ?'), 'Nodes uses the shared parameter builder with its graph workflow')
check(buildRenderParams({ ...cfg, template: 'video_dub_lipsync', lipsync: false }, 'cpu', 'video').lipsync === true,
  'lip-sync workflow enables the same stage in estimates and render parameters')
check(buildRenderParams({ ...cfg, template: 'video_dub_lipsync', lipsync: false }, 'cpu', 'video', 'video_dub').lipsync === false,
  'muted node overrides a previously selected Dashboard lip-sync workflow')
check(buildRenderParams({ ...cfg, template: 'video_dub', lipsync: false }, 'cpu', 'video').lipsync === false,
  'plain video preserves disabled lip sync')
check(buildRenderParams({ ...cfg, template: 'video_dub', lipsync: true }, 'cpu', 'video').lipsync === true,
  'plain video preserves optional enabled lip sync')
check(read('src/pages/Dashboard.tsx').includes('value={v.id}'), 'voice dropdown uses IDs')
check(config.includes('subtitles: "includeSubtitles"'), 'subtitle node shares Dashboard state')
check(read('src/App.tsx').includes('discardInterruptedRender(interrupted.recovery_token)'), 'explicit discard acknowledges the offered recovery record')
console.log(`${checks} architecture UI contract checks passed`)
