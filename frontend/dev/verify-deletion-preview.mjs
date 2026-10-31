// Verify the production confirmation text; no real deletion or bridge calls.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const destination = path.join(root, 'node_modules', '.deletion-preview.mjs')
fs.writeFileSync(destination, ts.transpileModule(fs.readFileSync(path.join(root, 'src/lib/deletion-preview.ts'), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText)
const { describeDeletion, describeDeletionResult } = await import(pathToFileURL(destination))
const preview = describeDeletion({ ok: true, files: 2, bytes: 1250000,
  candidates: [{ path: 'outputs/render.mp4', files: 2, bytes: 1250000 }],
  retained: [{ path: 'models/shared.pth', reason: 'Shared model.' }] })
let checks = 0
function check(condition, label) { assert.ok(condition, label); checks++; console.log('PASS', label) }
check(preview.includes('2 files (1.25 MB)'), 'confirmation quantifies deletion')
check(preview.includes('outputs/render.mp4'), 'confirmation names affected paths')
check(preview.includes('Kept: models/shared.pth. Shared model.'), 'confirmation explains retained files')
check(describeDeletion({ ok: true }).includes('0 files'), 'connection-only removal has zero deletion count')
const result = describeDeletionResult({ ok: false, message: 'File busy', removed: ['temp'], remaining: ['outputs'], retained: [{ path: 'model', reason: 'Unverified' }] })
check(result.includes('File busy'), 'failure reason stays visible')
check(result.includes('Processed: temp') && result.includes('Remaining: outputs'), 'partial outcome names finished and unfinished paths')
check(result.includes('Kept: model. Unverified'), 'result states retained files')
check(describeDeletionResult({ ok: false }).includes('Review the files again'), 'missing diagnostic has actionable fallback')
console.log(`Deletion preview UI checks passed: ${checks}`)
