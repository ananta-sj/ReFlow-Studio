// Exercise the same pure state transitions used by the production render hook.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const destination = path.join(root, 'node_modules', '.cancellation-state.mjs')
const source = fs.readFileSync(path.join(root, 'src/lib/render-state.ts'), 'utf8')
fs.writeFileSync(destination, ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText)
const { INITIAL, applyRenderEvent, isRenderBusy } = await import(pathToFileURL(destination))
let checks = 0
const check = (value, label) => { assert.ok(value, label); checks++; console.log('PASS', label) }
let state = applyRenderEvent(INITIAL, 'render_started', { inputPath: 'one.mp4' })
check(isRenderBusy(state) && state.inputPath === 'one.mp4', 'accepted job is busy')
state = applyRenderEvent(state, 'progress', { percent: 40, status: 'Generating speech' })
state = applyRenderEvent(state, 'stage', { stageId: 'tts_rvc' })
state = applyRenderEvent(state, 'render_stopping', {})
check(state.status === 'stopping' && isRenderBusy(state), 'stop acknowledgment remains busy')
check(state.percent === 40 && state.activeStageId === 'tts_rvc', 'stop retains current phase and progress')
check(state.statusText.includes('waiting for active work'), 'stop message explains pending active work')
for (const [event, payload] of [
  ['progress', { percent: 99, status: 'Done' }],
  ['stage', { stageId: 'output' }],
  ['source_language', { source_name: 'late source' }],
]) check(applyRenderEvent(state, event, payload) === state, `${event} cannot replace stopping state`)
state = applyRenderEvent(state, 'render_stopped', {})
check(state === INITIAL && !isRenderBusy(state), 'only final stopped event returns idle')
state = applyRenderEvent(state, 'render_started', { inputPath: 'two.wav' })
check(state.inputPath === 'two.wav' && state.sourceFeedback === null, 'next job starts with fresh feedback')
state = applyRenderEvent(state, 'render_finished', { outputPath: 'result.wav' })
check(state.status === 'finished' && !isRenderBusy(state) && state.outputPath === 'result.wav', 'normal completion remains supported')
state = applyRenderEvent(state, 'render_started', { inputPath: 'three.wav' })
state = applyRenderEvent(state, 'render_error', { message: 'real failure' })
check(state.status === 'error' && !isRenderBusy(state) && state.errorMessage === 'real failure', 'real failure remains visible')
check(applyRenderEvent(state, 'unknown-event', {}) === state, 'unknown events leave state intact')
console.log(`Cancellation UI state checks passed: ${checks}`)
