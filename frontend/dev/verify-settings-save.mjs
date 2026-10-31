// Test production save ordering with deferred and rejected backend responses.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const out = path.join(root, 'node_modules', '.settings-save-checks')
fs.mkdirSync(out, { recursive: true })
fs.writeFileSync(path.join(out, 'settings-save.mjs'), ts.transpileModule(
  fs.readFileSync(path.join(root, 'src/lib/settings-save.ts'), 'utf8'),
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } },
).outputText)
const { createSettingsSaver } = await import(pathToFileURL(path.join(out, 'settings-save.mjs')))
const save = createSettingsSaver()
const calls = []
let release
const first = save(() => { calls.push('first'); return new Promise(resolve => { release = resolve }) })
const second = save(async () => { calls.push('second'); return 'confirmed second' })
await Promise.resolve()
assert.deepEqual(calls, ['first'])
console.log('PASS later save waits for pending backend response')
release('confirmed first')
assert.equal(await first, 'confirmed first')
assert.equal(await second, 'confirmed second')
assert.deepEqual(calls, ['first', 'second'])
console.log('PASS confirmed values and submission order preserved')
await assert.rejects(save(async () => { throw new Error('disk full') }), /disk full/)
console.log('PASS save failure reaches caller')
assert.equal(await save(async () => 'retry persisted'), 'retry persisted')
console.log('PASS rejected save does not block later retry')
const change = save(async () => { calls.push('change'); return 'changed' })
const reset = save(async () => { calls.push('reset'); return 'defaults' })
await Promise.all([change, reset])
assert.deepEqual(calls.slice(-2), ['change', 'reset'])
console.log('PASS reset follows earlier submitted changes')
const page = fs.readFileSync(path.join(root, 'src/pages/Settings.tsx'), 'utf8')
assert.ok(page.includes('setValues(persisted)') && !page.includes('setValues(next)'))
assert.ok(page.includes('catch (error)') && page.includes('await showSettingsError(error)'))
console.log('PASS Settings commits backend response and reports errors (source check)')
console.log('6 settings-save checks passed')
