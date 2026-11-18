const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function harness(file, imports) {
  const states = [], effects = [], pending = []
  let cursor = 0, writes = 0
  const react = {
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial
      return [states[i], value => { writes++; states[i] = typeof value === 'function' ? value(states[i]) : value }] },
    useRef(initial) { const i = cursor++; if (!(i in states)) states[i] = { current: initial }; return states[i] },
    useEffect(callback, deps) { const i = cursor++, old = effects[i]
      if (!old || deps.some((value, j) => value !== old.deps[j])) {
        effects[i] = { deps, cleanup: old?.cleanup }
        pending.push(() => { effects[i].cleanup?.(); effects[i].cleanup = callback() })
      }
    },
  }
  const filename = path.resolve(__dirname, 'src', file), module = { exports: {} }
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText
  vm.runInNewContext(code, { module, exports: module.exports, setTimeout, clearTimeout,
    require(name) { if (name === 'react') return react; if (name in imports) return imports[name]
      if (name.startsWith('@/')) return new Proxy({}, { get: (_, key) => key })
      return require(name)
    },
  }, { filename })
  return {
    render(props) { cursor = 0; return Object.values(module.exports)[0](props) },
    effects() { while (pending.length) pending.shift()() },
    writes: () => writes,
    unmount() { effects.forEach(effect => effect?.cleanup?.()) },
  }
}
const flush = async () => { for (let i = 0; i < 35; i++) await Promise.resolve() }
function nodes(tree) { if (tree == null || typeof tree !== 'object') return []
  if (Array.isArray(tree)) return tree.flatMap(nodes)
  return [tree, ...nodes(tree.props?.children)] }
function text(tree) { if (tree == null || typeof tree === 'boolean') return ''
  if (typeof tree !== 'object') return String(tree)
  return Array.isArray(tree) ? tree.map(text).join('') : text(tree.props?.children) }
function button(tree, label) { return nodes(tree).find(node => node.props?.onClick && (node.props['aria-label'] === label || text(node) === label)) }
function closeButton(tree) { return button(tree, 'Close window') ?? nodes(tree).filter(node => node.type === 'button').at(-1) }
function titleFixture(overrides = {}, answer = true) {
  const alerts = [], calls = []
  const bridge = { getSettings: async () => ({ values: { clear_temp_on_exit: false } }), closeWindow: async () => { calls.push('close') }, ...overrides }
  const h = harness('components/shell/TitleBar.tsx', {
    '@/lib/startup-timeout': { withStartupTimeout: operation => operation },
    '@/lib/api': { bridge }, '@/lib/use-render': { useRenderJob: () => ({ isRunning: true }) },
    '@/lib/use-confirm': { confirmAction: async options => { alerts.push(options); return !options.alertOnly && answer } },
  })
  return { ...h, alerts, calls, props: { theme: 'dark', onNavigate() {}, onToggleTheme() {} } }
}

test('close settings rejection gives a safe error without closing', async () => {
  const f = titleFixture({ getSettings: async () => { throw new Error('sensitive upstream text') } })
  await assert.doesNotReject(async () => closeButton(f.render(f.props)).props.onClick())
  assert.equal(f.calls.length, 0)
  assert.equal(f.alerts.at(-1)?.title, 'Close unavailable')
  assert.ok(!f.alerts.at(-1).description.includes('sensitive'))
})
test('failed close request is awaited, reported and can be retried', async () => {
  let calls = 0
  const f = titleFixture({ closeWindow: async () => { if (++calls === 1) throw new Error('private') } })
  await assert.doesNotReject(async () => closeButton(f.render(f.props)).props.onClick())
  assert.equal(f.alerts.at(-1)?.title, 'Close unavailable')
  await closeButton(f.render(f.props)).props.onClick()
  assert.equal(calls, 2)
})
test('duplicate close clicks share one pending confirmation', async () => {
  let resolveSettings, reads = 0
  const f = titleFixture({ getSettings: () => { reads++; return new Promise(resolve => { resolveSettings = resolve }) } })
  const action = closeButton(f.render(f.props)).props.onClick
  const first = action(), second = action()
  assert.equal(reads, 1)
  resolveSettings({ values: { clear_temp_on_exit: false } })
  await Promise.all([first, second]); assert.equal(f.calls.length, 1)
})

test('title-bar controls have six distinct accessible names and a theme target', () => {
  const React = require('react'), { renderToStaticMarkup } = require('react-dom/server')
  const filename = path.resolve(__dirname, 'src/components/shell/TitleBar.tsx'), module = { exports: {} }
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText
  vm.runInNewContext(code, { module, exports: module.exports, require(name) {
    if (name === '@/lib/use-render') return { useRenderJob: () => ({ isRunning: false }) }
    if (name === '@/lib/api') return { bridge: {} }
    if (name === '@/lib/startup-timeout') return { withStartupTimeout: operation => operation }
    if (name === '@/lib/use-confirm') return { confirmAction() {} }
    if (name === '@/components/shared/HelpTooltip') return { HelpTooltip: () => null }
    return require(name)
  } })
  const html = renderToStaticMarkup(React.createElement(module.exports.TitleBar, { theme: 'dark', onNavigate() {}, onToggleTheme() {} }))
  for (const label of ['Open logs','Switch to light theme','Minimize to tray','Minimize window','Maximize or restore window','Close window']) assert.ok(html.includes(`aria-label="${label}"`), label)
})

function dashboardFixture() {
  let fail = true, starts = 0
  const cfg = { template: 'video_dub', lang: 'hi', sourceLanguage: 'auto', voice: 'CLONED_USER', taskPriority: 75, parallelWorkers: 1, qualityIdx: 0 }
  const bridge = {
    listModels: async () => [{ id: 'voice', status: 'installed' }],
    listPipelineTemplates: async () => ({ video_dub: { input_kind: 'video', label: 'Video dub' } }),
    getHardwareSnapshot: async () => ({ devices: [{ id: 'cpu', label: 'CPU' }], vram_used_mb: null, vram_total_mb: null }),
    listLanguages: async () => { if (fail) throw new Error('offline'); return [{ code: 'hi', name: 'Hindi' }] },
    listSourceLanguages: async () => [{ code: 'ja', name: 'Japanese' }],
    estimateJobAllDevices: async () => ({}),
  }
  const h = harness('pages/Dashboard.tsx', {
    '@/lib/api': { bridge }, '@/lib/use-queue': { useQueue: () => [{ id: 'one', input_path: 'episode.mp4' }], addToQueue() {} },
    '@/lib/use-render-config': { QUALITY_STEPS: [1,2,4], useRenderConfig: () => cfg, updateConfig() { throw new Error('must retain selections') } },
    '@/lib/use-experience': { levelAtLeast: () => false },
    '@/lib/use-render': { useRenderJob: () => ({ status: 'idle', isRunning: false, startBatch: async () => { starts++; return { ok: true } } }) },
    '@/lib/render-params': { buildRenderParams: () => ({ lang: cfg.lang }) },
    '@/lib/utils': { cn: (...parts) => parts.filter(Boolean).join(' ') },
    '@/lib/eta': { jobMemoryBudget: () => null, projectedLoadPercent: () => null },
    '@/lib/use-confirm': { confirmAction: async () => true },
    '@/lib/startup-timeout': { withStartupTimeout: operation => operation },
  })
  return { ...h, cfg, bridge, starts: () => starts, recover() { fail = false }, props: { selectedDeviceId: 'cpu', level: 'basic', onNavigate() {} } }
}

test('dashboard exposes resource failure, blocks start and retries without changing selection', async () => {
  const f = dashboardFixture()
  f.render(f.props); f.effects(); await flush()
  let tree = f.render(f.props)
  assert.ok(nodes(tree).some(node => node.props?.role === 'alert' && /language/i.test(text(node))))
  assert.equal(button(tree, 'START VIDEO BATCH').props.disabled, true)
  await button(tree, 'START VIDEO BATCH').props.onClick()
  assert.equal(f.starts(), 0)
  f.recover(); button(tree, 'Retry loading options').props.onClick()
  f.render(f.props); f.effects(); await flush(); tree = f.render(f.props)
  assert.equal(button(tree, 'START VIDEO BATCH').props.disabled, false)
  assert.equal(f.cfg.lang, 'hi')
  assert.ok(!nodes(tree).some(node => node.props?.role === 'alert' && /could not load/i.test(text(node))))
  f.unmount()
})




for (const method of ['listModels', 'listPipelineTemplates', 'getHardwareSnapshot', 'listLanguages', 'listSourceLanguages']) {
  test(`dashboard reports ${method} rejection without starting a job`, async () => {
    const f = dashboardFixture(); f.recover()
    f.bridge[method] = async () => { throw new Error('private upstream text') }
    f.render(f.props); f.effects(); await flush()
    const tree = f.render(f.props)
    assert.ok(nodes(tree).some(node => node.props?.role === 'alert' && /Could not load/.test(text(node))))
    assert.equal(button(tree, 'START VIDEO BATCH').props.disabled, true)
    assert.ok(!text(tree).includes('private upstream'))
    f.unmount()
  })
}

test('unmounted dashboard ignores late option responses', async () => {
  const f = dashboardFixture(); f.recover()
  let finish
  f.bridge.listLanguages = () => new Promise(resolve => { finish = resolve })
  f.render(f.props); f.effects(); await flush(); f.unmount()
  const before = f.writes()
  finish([{ code: 'hi', name: 'Hindi' }]); await flush()
  assert.equal(f.writes(), before)
})

test('unavailable saved selections are kept and cannot start a job', async () => {
  const f = dashboardFixture(); f.recover(); f.cfg.lang = 'unavailable'
  f.render(f.props); f.effects(); await flush()
  const tree = f.render(f.props)
  assert.equal(button(tree, 'START VIDEO BATCH').props.disabled, true)
  await button(tree, 'START VIDEO BATCH').props.onClick()
  assert.equal(f.starts(), 0)
  assert.equal(f.cfg.lang, 'unavailable')
  assert.ok(text(tree).includes('Choose available options'))
  f.unmount()
})


test('cancelled close keeps the app open and enables another attempt', async () => {
  const f = titleFixture({}, false)
  await closeButton(f.render(f.props)).props.onClick()
  assert.equal(f.calls.length, 0)
  assert.equal(closeButton(f.render(f.props)).props.disabled, false)
})

test('accepted close stays disabled while backend shutdown completes', async () => {
  const f = titleFixture()
  await closeButton(f.render(f.props)).props.onClick()
  assert.equal(f.calls.length, 1)
  assert.equal(closeButton(f.render(f.props)).props.disabled, true)
  assert.equal(closeButton(f.render(f.props)).props['aria-busy'], true)
})
