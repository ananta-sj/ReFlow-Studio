// Use the already-installed TypeScript compiler and Node assertions; no SDK.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const ts = require('../frontend/node_modules/typescript');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/src/lib/eta.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const exportsObject = {};
vm.runInNewContext(compiled, { exports: exportsObject });
const { jobMemoryBudget, projectedLoadPercent } = exportsObject;
const results = [];
function check(name, run) { run(); results.push({name, passed:true}); }
check('Selected GPU uses its budget instead of another GPU aggregate', () => {
  const estimate = {peak_vram_mb:6400, peak_vram_by_device_mb:{'cuda:0':6400, 'cuda:1':900}};
  assert.equal(jobMemoryBudget(estimate, 'cuda:1'), 900);
  assert.equal(projectedLoadPercent(100, 2000, jobMemoryBudget(estimate, 'cuda:1')), 50);
});
check('Explicit unknown stays unknown even with a legacy aggregate', () => {
  assert.equal(jobMemoryBudget({peak_vram_mb:6400, peak_vram_by_device_mb:{'cuda:1':null}}, 'cuda:1'), null);
  assert.equal(projectedLoadPercent(100, 2000, null), null);
});
check('A supplied map with no selected-device allocation means zero additional budget', () => {
  assert.equal(jobMemoryBudget({peak_vram_mb:6400, peak_vram_by_device_mb:{'cuda:0':6400}}, 'cuda:1'), 0);
});
check('Older backend response remains supported', () => {
  assert.equal(jobMemoryBudget({peak_vram_mb:900}, 'cuda:1'), 900);
});
check('Missing estimate is not silently converted to zero', () => {
  assert.equal(jobMemoryBudget(undefined, 'cuda:0'), undefined);
  assert.equal(projectedLoadPercent(100, 2000, undefined), null);
});
check('Missing telemetry prevents a capacity claim', () => {
  assert.equal(projectedLoadPercent(null, 2000, 900), null);
  assert.equal(projectedLoadPercent(100, null, 900), null);
});
check('Invalid numbers do not poison the gauge', () => {
  for (const total of [0, -1, NaN, Infinity]) assert.equal(projectedLoadPercent(100, total, 900), null);
  for (const budget of [-1, NaN, Infinity]) assert.equal(projectedLoadPercent(100, 2000, budget), null);
  assert.equal(projectedLoadPercent(NaN, 2000, 900), null);
});
check('Known capacity comparison includes current use and caps the display', () => {
  assert.equal(projectedLoadPercent(100, 2000, 900), 50);
  assert.equal(projectedLoadPercent(1500, 2000, 900), 100);
});
const receipt = {checks:results, source:'frontend/src/lib/eta.ts', source_sha256:crypto.createHash('sha256').update(source).digest('hex'), passed:true};
fs.writeFileSync(path.join(root, 'docs/validation/2026-10-09-resource-routing-frontend-contracts.json'), JSON.stringify(receipt, null, 2));
console.log(JSON.stringify(receipt, null, 2));
