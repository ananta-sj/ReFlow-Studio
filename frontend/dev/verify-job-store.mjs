// Exercise shared production state with a simulated bridge; no inference.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const out = path.join(root, 'node_modules', '.job-store-checks')
fs.mkdirSync(out, { recursive: true })
for (const name of ['render-state', 'job-store']) {
  const text = ts.transpileModule(fs.readFileSync(path.join(root, 'src/lib', name + '.ts'), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
  }).outputText.replace(/from ['"]\.\/render-state['"]/g, "from './render-state.mjs'")
  fs.writeFileSync(path.join(out, name + '.mjs'), text)
}
const { createJobStore } = await import(pathToFileURL(path.join(out, 'job-store.mjs')))
const { INITIAL } = await import(pathToFileURL(path.join(out, 'render-state.mjs')))
const snap = (revision, extra = {}) => ({ sessionId: 'backend-one', revision,
  render: { ...INITIAL, status: 'running', inputPath: 'one.mp4' }, queue: [{ id: 'one', input_path: 'one.mp4', status: 'processing' }],
  busy: true, paused: false, lastEventAt: 1, ...extra })
let checks = 0
const check = (condition, label) => { assert.ok(condition, label); checks++; console.log('PASS', label) }
const store = createJobStore()
let notified = 0
const off = store.subscribe(() => notified++)
store.apply(snap(1))
check(notified === 1 && store.getSnapshot().busy, 'live event reaches mounted subscriber')
off()
store.apply(snap(2, { render: { ...INITIAL, status: 'stopping', sourceFeedback: { source_name: 'Hindi' } } }))
let remounted = 0
const offAgain = store.subscribe(() => remounted++)
check(store.getSnapshot().render.status === 'stopping' && store.getSnapshot().render.sourceFeedback.source_name === 'Hindi', 'unmounted state and source feedback survive remount')
store.apply(snap(1))
check(store.getSnapshot().revision === 2 && remounted === 0, 'older pushed revision cannot regress progress')
let resolveOld
const oldRead = store.refresh(() => new Promise((resolve) => { resolveOld = resolve }))
store.apply(snap(4, { paused: true }))
resolveOld(snap(3))
await oldRead
check(store.getSnapshot().revision === 4 && store.getSnapshot().paused, 'delayed snapshot cannot undo a newer event')
const before = store.getSnapshot()
const rejected = await store.act(async () => ({ ok: false, message: 'Busy' }), async () => before)
check(!rejected.ok && rejected.message === 'Busy', 'start rejection is returned to caller')
check(store.getSnapshot().queue[0].id === 'one' && store.getSnapshot().busy, 'rejection keeps input and active job state')
const disconnected = await store.act(async () => { throw new Error('Disconnected') }, async () => { throw new Error('No snapshot') })
check(!disconnected.ok && store.getSnapshot() === before, 'transport failure retains last authoritative state')
await store.act(async () => ({ ok: true }), async () => snap(5, { busy: false, render: { ...INITIAL, status: 'finished', outputPath: 'output.wav' } }))
check(store.getSnapshot().render.outputPath === 'output.wav' && !store.getSnapshot().busy, 'accepted action hydrates backend output and idle acknowledgment')
const cleanup = snap(6, { render: { ...INITIAL, status: 'finished', outputPath: 'output.wav' } })
store.apply(cleanup)
check(store.getSnapshot().busy && store.getSnapshot().render.status === 'finished', 'published output does not imply cleanup is idle')
store.apply(snap(7, { busy: false, render: INITIAL }))
check(!store.getSnapshot().busy && store.getSnapshot().render.status === 'idle', 'final stopped snapshot makes controls idle')
let resolveNewer
const newerRead = store.refresh(() => new Promise((resolve) => { resolveNewer = resolve }))
store.apply(snap(8))
resolveNewer(snap(9))
await newerRead
check(store.getSnapshot().revision === 9, 'newer same-session response remains usable after a concurrent event')
store.apply(snap(1, { sessionId: 'backend-two', busy: false, render: INITIAL, queue: [] }))
store.apply(snap(99))
check(store.getSnapshot().sessionId === 'backend-two', 'retired backend events cannot replace a new backend session')
let resolveUnknown
const unknownRead = store.refresh(() => new Promise((resolve) => { resolveUnknown = resolve }))
store.apply(snap(2, { sessionId: 'backend-two', render: INITIAL, busy: false }))
resolveUnknown(snap(100, { sessionId: 'unseen-old-backend' }))
await unknownRead
check(store.getSnapshot().sessionId === 'backend-two', 'in-flight response from an unknown old session is refused after a newer event')
offAgain()
console.log(`Shared job store checks passed: ${checks}`)
