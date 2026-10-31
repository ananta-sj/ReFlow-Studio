// Uses existing React/TypeScript and Node assertions; no additional test framework.
import assert from 'node:assert/strict'
import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const stored = new Map([['reflow.renderConfig', JSON.stringify({ template: 'subtitle_translate', lang: 'en' })]])
globalThis.localStorage = { getItem: (key) => stored.get(key) ?? null, setItem: (key, value) => stored.set(key, value) }
const savedPreferences = {}
globalThis.window = { pywebview: { api: {
  set_node_enabled: async () => ({ ok: true }),
  get_ui_preferences: async () => ({ ...savedPreferences }),
  update_ui_preferences: async partial => Object.assign(savedPreferences, partial),
} } }
const frontend = fileURLToPath(new URL('../', import.meta.url))
const src = path.join(frontend, 'src')
const output = path.join(frontend, 'node_modules', '.source-language-ssr')
assert.ok(output.startsWith(path.join(frontend, 'node_modules') + path.sep))
function files(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => entry.isDirectory()
    ? files(path.join(directory, entry.name)) : [path.join(directory, entry.name)])
}
for (const file of files(src).filter(file => /\.tsx?$/.test(file) && !file.endsWith('.d.ts'))) {
  const rewrite = context => node => {
    const visit = current => {
      if ((ts.isImportDeclaration(current) || ts.isExportDeclaration(current)) && current.moduleSpecifier && ts.isStringLiteral(current.moduleSpecifier)) {
        const specifier = current.moduleSpecifier.text
        if (specifier.startsWith('@/') || specifier.startsWith('.')) {
          const target = specifier.startsWith('@/') ? path.join(src, specifier.slice(2)) : path.resolve(path.dirname(file), specifier)
          const actual = [target, target+'.ts', target+'.tsx'].find(value => fs.existsSync(value) && fs.statSync(value).isFile())
          assert.ok(actual, 'Cannot resolve test import '+specifier)
          const modulePath = path.join(output, path.relative(src, actual)).replace(/\.tsx?$/, '.mjs')
          const value = ts.factory.createStringLiteral(pathToFileURL(modulePath).href)
          if (ts.isImportDeclaration(current)) return ts.factory.updateImportDeclaration(current, current.modifiers, current.importClause, value, current.attributes)
          return ts.factory.updateExportDeclaration(current, current.modifiers, current.isTypeOnly, current.exportClause, value, current.attributes)
        }
      }
      return ts.visitEachChild(current, visit, context)
    }
    return ts.visitNode(node, visit)
  }
  const transpiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    fileName: file, compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023, jsx: ts.JsxEmit.ReactJSX },
    transformers: { after: [rewrite] }
  })
  const destination = path.join(output, path.relative(src, file)).replace(/\.tsx?$/, '.mjs')
  fs.mkdirSync(path.dirname(destination), { recursive: true })
  fs.writeFileSync(destination, transpiled.outputText)
}
const load = name => import(pathToFileURL(path.join(output, name.replace('/src/', '').replace(/\.tsx?$/, '.mjs'))).href)
let checks = 0
const check = (condition, description) => { assert.ok(condition, description); checks++; console.log('PASS '+description) }
try {
  const { SourceLanguageReport } = await load('/src/components/shared/SourceLanguageReport.tsx')
  const base = { source_code: 'hi', source_name: 'Hindi', origin: 'detected', resolved: true, detected_language: 'hi', detected_name: 'Hindi', probability: 0.8, minimum_confidence: 0.8 }
  const render = (feedback) => renderToStaticMarkup(createElement(SourceLanguageReport, { feedback }))
  const automatic = render(base)
  check(automatic.includes('Hindi (Auto)') && automatic.includes('80.00% confidence'), 'accepted Auto source and confidence are displayed')
  const low = render({ ...base, probability: 0.79999, resolved: false })
  check(low.includes('79.99% confidence') && !low.includes('80.00%'), 'below-threshold confidence is not rounded up to an accepted value')
  check(low.includes('manual selection') && low.includes('may infer it'), 'unresolved feedback explains fixed-provider and prompt-provider behavior')
  const manual = render({ ...base, source_code: 'fr', source_name: 'French', origin: 'manual' })
  check(manual.includes('French (manual override)') && manual.includes('Detected source: Hindi'), 'manual translation source remains distinct from detected source')
  const missing = render({ ...base, detected_language: null, detected_name: null, probability: null, source_code: null, source_name: null, origin: 'unknown', resolved: false })
  check(missing.includes('Unavailable') && missing.includes('confidence unavailable') && !missing.includes('null'), 'missing language/confidence render without fabricated values')
  check(automatic.includes('role="status"') && automatic.includes('aria-live="polite"'), 'feedback uses an accessible live status region')
  const escaped = render({ ...base, detected_name: null, detected_language: '<script>fake</script>' })
  check(!escaped.includes('<script>fake</script>') && escaped.includes('&lt;script&gt;'), 'provider language labels are escaped as text')
  const { loadConfigDefaults, updateConfig } = await load('/src/lib/use-render-config.ts')
  const { initializePreferences, flushPreferences } = await load('/src/lib/preference-storage.ts')
  await initializePreferences()
  await loadConfigDefaults()
  await flushPreferences()
  check(JSON.parse(savedPreferences['reflow.renderConfig']).sourceLanguage === 'auto', 'legacy saved settings migrate to Auto')
  updateConfig({ sourceLanguage: 'fr' })
  await flushPreferences()
  check(JSON.parse(savedPreferences['reflow.renderConfig']).sourceLanguage === 'fr', 'manual source is persisted with render configuration')
  const reloaded = await import(pathToFileURL(path.join(output, 'lib/use-render-config.mjs')).href + '?manual-reload')
  await reloaded.loadConfigDefaults()
  const snapshot = renderToStaticMarkup(createElement(() => createElement('span', null, reloaded.useRenderConfig().sourceLanguage)))
  check(snapshot.includes('fr'), 'manual source restores after a fresh configuration load')
  const { Dashboard } = await load('/src/pages/Dashboard.tsx')
  const { buildRenderParams } = await load('/src/lib/render-params.ts')
  const cfg = { template: 'video_dub', lang: 'en', sourceLanguage: 'fr', voice: 'Actor', refAudio: null, keepBg: true,
    lipsync: true, enhance: true, burnSubs: true, contentFilter: true, taskPriority: 75, qualityIdx: 0, parallelWorkers: 2 }
  for (const kind of ['video', 'audio', 'subtitle']) {
    for (const selected of ['fr', 'auto']) {
      const params = buildRenderParams({ ...cfg, sourceLanguage: selected }, 'cpu', kind)
      check(params.source_language === selected && params.lang === 'en', kind+' parameters forward '+selected+' independently of target')
      check(JSON.parse(JSON.stringify(params)).source_language === selected, kind+' source survives queue/resume JSON serialization for '+selected)
    }
  }
  check(!('voice' in buildRenderParams(cfg, 'cpu', 'subtitle')), 'subtitle parameters do not introduce speech settings')
  check(!('lipsync' in buildRenderParams(cfg, 'cpu', 'audio')), 'audio parameters do not introduce video settings')
  const html = renderToStaticMarkup(createElement(Dashboard, { selectedDeviceId: 'cpu', level: 'expert', onNavigate: () => {} }))
  check(html.includes('Source Language') && html.includes('Target Language'), 'Dashboard renders separate source and target controls')
  check(html.includes('&quot;source_language&quot;: &quot;fr&quot;'), 'expert parameter preview includes the manual source')
  console.log('Source UI checks passed: '+checks)
} finally {
  // The approved workspace node_modules cleanup removes generated SSR modules.
}
