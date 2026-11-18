const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function fixture() {
  const timers = new Map(), listeners = new Set(), cache = new Map()
  let next = 0
  const window = {
    addEventListener(name, callback) { if (name === 'pywebviewready') listeners.add(callback) },
    removeEventListener(name, callback) { if (name === 'pywebviewready') listeners.delete(callback) },
    __reflow: { dispatch() {} },
  }
  function load(name) {
    const filename = path.resolve(__dirname, 'src/lib', name + '.ts')
    if (cache.has(filename)) return cache.get(filename).exports
    const module = { exports: {} }; cache.set(filename, module)
    const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText
    vm.runInNewContext(code, { module, exports: module.exports, window,
      localStorage: { getItem() { return null } }, console: { warn() {} },
      setTimeout(callback) { const id = ++next; timers.set(id, callback); return id },
      clearTimeout(id) { timers.delete(id) },
      require(specifier) { return load(specifier.replace(/^\.\//, '')) },
    }, { filename })
    return module.exports
  }
  return { load, window, timers, listeners,
    expire() { for (const [id, callback] of [...timers]) { timers.delete(id); callback() } },
    ready(api = {}) { window.pywebview = { api }; for (const callback of [...listeners]) callback() },
  }
}
const flush = async () => { for (let i = 0; i < 15; i++) await Promise.resolve() }

test('missing bridge rejects, removes listener and permits a fresh retry', async () => {
  const f = fixture(), api = f.load('api')
  let rejected = false
  const first = api.whenReady().catch(() => { rejected = true })
  await flush(); f.expire(); await flush()
  assert.equal(rejected, true, 'startup must not wait forever for the bridge')
  await first
  assert.equal(f.listeners.size, 0)
  const retry = api.whenReady(); f.ready(); await retry
  assert.equal(f.listeners.size, 0)
  assert.equal(f.timers.size, 0)
})

test('concurrent bridge readers share one listener and accept delayed readiness', async () => {
  const f = fixture(), api = f.load('api')
  const first = api.whenReady(), second = api.whenReady()
  assert.equal(first, second)
  assert.equal(f.listeners.size, 1)
  f.ready(); await first
  assert.equal(f.listeners.size, 0)
  assert.equal(f.timers.size, 0)
})

test('startup deadline ignores a late result and releases timers', async () => {
  const f = fixture(), { withStartupTimeout } = f.load('startup-timeout')
  let resolve
  const late = new Promise(done => { resolve = done })
  const result = withStartupTimeout(late, 'Startup read timed out').catch(error => error.message)
  f.expire(); await flush()
  assert.equal(await result, 'Startup read timed out')
  resolve('late'); await flush()
  assert.equal(await result, 'Startup read timed out')
  assert.equal(await withStartupTimeout(Promise.resolve('ready'), 'timeout'), 'ready')
  assert.equal(f.timers.size, 0)
})

test('failed preference hydration is visible and retry preserves saved values', async () => {
  const f = fixture()
  let fail = true
  f.ready({ get_ui_preferences: async () => { if (fail) throw new Error('offline'); return { 'reflow-theme': 'light' } } })
  const prefs = f.load('preference-storage')
  await assert.rejects(prefs.initializePreferences())
  fail = false; await prefs.initializePreferences()
  assert.equal(prefs.preferenceStorage.getItem('reflow-theme'), 'light')
  fail = true; await assert.rejects(prefs.initializePreferences())
  assert.equal(prefs.preferenceStorage.getItem('reflow-theme'), 'light')
})
function componentModule(relative, imports, globals = {}) {
  const filename = path.resolve(__dirname, 'src', relative)
  const module = { exports: {} }
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText
  vm.runInNewContext(code, { module, exports: module.exports,
    require(name) { if (name in imports) return imports[name]; return require(name) }, ...globals }, { filename })
  return module.exports
}

test('startup error renders one accessible retry control', () => {
  const React = require('react')
  const { renderToStaticMarkup } = require('react-dom/server')
  const passthrough = tag => ({ children, className, role }) => React.createElement(tag, { className, role }, children)
  const { BootScreen } = componentModule('components/shell/BootScreen.tsx', {
    'motion/react': { motion: { div: passthrough('div'), span: passthrough('span') }, AnimatePresence: ({ children }) => children },
  })
  const html = renderToStaticMarkup(React.createElement(BootScreen, {
    visible: true, statusText: 'Needs attention', error: 'Connection failed', onRetry() {},
  }))
  assert.equal((html.match(/Retry startup/g) || []).length, 1)
  assert.equal((html.match(/role="alert"/g) || []).length, 1)
})

test('bootstrap displays pending/error states and serializes retries before mounting App', async () => {
  let output, calls = 0, rejectFirst, resolveRetry
  const first = new Promise((_, reject) => { rejectFirst = reject })
  const retry = new Promise(resolve => { resolveRetry = resolve })
  componentModule('main.tsx', {
    './index.css': {}, './App.tsx': { __esModule: true, default: 'App' },
    './components/shell/BootScreen': { BootScreen: 'BootScreen' },
    './lib/use-logs': { initializeLogs() {} },
    './lib/preference-storage': { initializePreferences() { return ++calls === 1 ? first : retry } },
    'react-dom/client': { createRoot() { return { render(tree) { output = tree } } } },
  }, { document: { getElementById() { return {} } } })
  assert.equal(output.type, 'BootScreen', 'render a shell before preferences finish')
  rejectFirst(new Error('offline')); await flush()
  assert.ok(output.props.error)
  const retryStartup = output.props.onRetry
  retryStartup(); retryStartup()
  assert.equal(calls, 2, 'double-click must not start parallel hydration')
  resolveRetry(); await flush()
  assert.equal(output.props.children.type, 'App')
})

test('integrity transport failure offers retry; returned ok:false still opens the app', async () => {
  const f = fixture(), states = [], effects = [], pending = []
  let cursor = 0, calls = 0
  const react = {
    useState(initial) {
      const index = cursor++
      if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value }]
    },
    useEffect(callback, deps) {
      const index = cursor++, prev = effects[index]
      if (!prev || deps.some((value, i) => value !== prev.deps[i])) {
        effects[index] = { deps, cleanup: prev?.cleanup }
        pending.push(() => { effects[index].cleanup?.(); effects[index].cleanup = callback() })
      }
    },
  }
  const bridge = {
    getHardwareSnapshot: async () => ({ devices: [], default_device_id: 'cpu' }),
    runIntegrityCheck: async () => { calls++; if (calls === 1) throw new Error('transport'); return { ok: false, message: 'Engine missing' } },
    getSettings: async () => ({ values: { onboarding_complete: true } }),
    captureHardwareProfile: async () => ({}), getInterruptedRender: async () => null,
  }
  const imports = {
    react, './lib/events': {}, '@/lib/startup-timeout': f.load('startup-timeout'),
    '@/lib/api': { bridge }, '@/lib/use-jobs': { initializeJobs() {}, runJobAction() { throw new Error('must not start jobs') } },
    '@/lib/use-theme': { useTheme: () => ({ theme: 'dark', toggle() {} }) },
    '@/lib/use-accent-color': { useAccentColor() {} },
    '@/lib/use-experience': { useExperienceLevel: () => ({ level: 'basic', setLevel() {} }), levelAtLeast: () => false },
    '@/lib/preference-storage': { preferenceStorage: { getItem: () => null, setItem() {} } },
    '@/lib/use-tour': { hasTourCompleted: () => true, startTour() {} },
    '@/lib/use-confirm': { ConfirmDialogHost: 'Dialog', confirmAction: async () => false, confirmChoice: async () => 'dismiss' },
  }
  for (const name of ['TitleBar','PrimaryNav','IconRail','BootScreen']) imports['@/components/shell/'+name] = { [name]: name }
  for (const name of ['SetupWizard','ProductTour']) imports['@/components/onboarding/'+name] = { [name]: name }
  for (const name of ['HardwareIntelligence','LogConsole']) imports['@/components/panels/'+name] = { [name]: name }
  imports['@/components/shared/CodeUpdateNotice'] = { CodeUpdateNotice: 'Notice' }
  for (const [file, name] of [['Dashboard','Dashboard'],['Nodes','NodesPage'],['Assets','AssetsPage'],['Marketplace','MarketplacePage'],['Logs','LogsPage'],['Settings','SettingsPage']]) imports['@/pages/'+file] = { [name]: name }
  const App = componentModule('App.tsx', imports, { window: f.window,
    setTimeout(callback) { const id = Symbol(); f.timers.set(id, callback); return id }, clearTimeout(id) { f.timers.delete(id) } }).default
  function render() { cursor = 0; return App() }
  function runEffects() { while (pending.length) pending.shift()() }
  render(); runEffects(); await flush()
  let boot = render().props.children[0]
  assert.ok(boot.props.error)
  assert.equal(boot.props.visible, true)
  boot.props.onRetry(); render(); runEffects(); await flush(); f.expire()
  boot = render().props.children[0]
  assert.equal(boot.props.error, null)
  assert.equal(boot.props.visible, false)
  assert.equal(boot.props.statusText, 'RUNTIME NEEDS ATTENTION')
  assert.equal(calls, 2)
})

test('timed-out preferences cannot overwrite saved values when the old read completes', async () => {
  const f = fixture()
  let read = async () => ({ 'reflow-theme': 'light' })
  f.ready({ get_ui_preferences: () => read() })
  const prefs = f.load('preference-storage')
  await prefs.initializePreferences()
  let resolveLate
  read = () => new Promise(resolve => { resolveLate = resolve })
  const failed = prefs.initializePreferences().catch(() => 'failed')
  await flush(); f.expire(); await flush()
  assert.equal(await failed, 'failed')
  resolveLate({ 'reflow-theme': 'dark' }); await flush()
  assert.equal(prefs.preferenceStorage.getItem('reflow-theme'), 'light')
})

test('long-running render calls do not acquire a startup deadline', async () => {
  const f = fixture()
  let finish
  f.ready({ start_render: () => new Promise(resolve => { finish = resolve }) })
  const result = f.load('api').bridge.startRender('fixture.mp4', {})
  await flush()
  assert.equal(f.timers.size, 0)
  finish({ ok: true }); assert.equal((await result).ok, true)
})

