import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { PACKAGES, MARKER, releaseBody, collectAssets, findPreviewRelease, hash, publish, validateExistingRelease } from '../publish_development_preview.mjs'

const SHA = 'a'.repeat(40)
const OTHER = 'b'.repeat(40)

async function fixture(run) {
  const folder = await mkdtemp(path.join(os.tmpdir(), 'reflow-preview-'))
  try {
    for (const name of Object.values(PACKAGES)) {
      const file = path.join(folder, name)
      await writeFile(file, `fixture package ${name}`)
      await writeFile(`${file}.sha256`, `${await hash(file)}  ${name}\n`)
    }
    await run(folder)
  } finally { await rm(folder, { recursive: true, force: true }) }
}

function server({ staleAt = Infinity, failUpload = Infinity, failPromotion = false, lostPromotionResponse = false } = {}) {
  const calls = []
  let heads = 0; let uploads = 0
  const release = { id: 1, prerelease: true, draft: false, body: MARKER,
    upload_url: 'https://uploads.github.com/release/1/assets{?name,label}' }
  const api = async (route, options = {}) => {
    calls.push({ route, ...options })
    if (route === '/git/ref/heads/main') return { object: { sha: ++heads >= staleAt ? OTHER : SHA } }
    if (route === '/releases/tags/development-preview') return { ...release }
    if (route === '/releases/1/assets?per_page=100&page=1') return [
      { id: 9, name: 'ReflowStudio-dev-old.zip' }, { id: 10, name: 'manual-user-attachment.txt' }]
    if (route.startsWith('https://uploads.github.com/')) {
      if (++uploads === failUpload) throw new Error('Upload failed')
      return { id: 100 + uploads, state: 'uploaded', size: 4 }
    }
    if (route === '/git/ref/tags/development-preview') return { object: { type: 'commit', sha: OTHER } }
    if (route === '/git/refs/tags/development-preview') return {}
    if (route === '/releases/1' && options.method === 'PATCH') {
      if (failPromotion) throw new Error('Metadata failed')
      Object.assign(release, options.body)
      if (lostPromotionResponse) throw new Error('Lost response')
      return release
    }
    if (route === '/releases/1') return { ...release }
    if (options.method === 'DELETE') return null
    throw new Error(`Unexpected request ${route}`)
  }
  const assets = [1, 2].map(n => ({ name: `ReflowStudio-dev-new${n}.zip`, file: '/fixture', bytes: 4, sha256: 'c'.repeat(64) }))
  return { api, calls, assets }
}

async function execute(state) {
  return publish({ ...state, repository: 'owner/repo', sha: SHA, runId: '123' })
}

test('complete packages require all four platforms, source and matching checksums', () => fixture(async folder => {
  const assets = await collectAssets(folder, SHA, '123', '1')
  assert.equal(assets.length, 5)
  assert.ok(assets.every(row => row.name.includes('aaaaaaaaaaaa-r123-a1')))
  await rm(path.join(folder, PACKAGES['macos-arm64']))
  await assert.rejects(collectAssets(folder, SHA, '123', '1'), /exactly four/)
}))

test('tampered package and unexpected private files block publication', () => fixture(async folder => {
  await writeFile(path.join(folder, PACKAGES.source), 'changed')
  await assert.rejects(collectAssets(folder, SHA, '123', '1'), /Checksum mismatch/)
  await writeFile(path.join(folder, 'settings.json'), '{}')
  await assert.rejects(collectAssets(folder, SHA, '123', '1'), /exactly four/)
}))

test('unowned and immutable releases are never modified', () => {
  for (const release of [{ prerelease: false, body: 'user release' }, { prerelease: true, body: 'user release' },
    { prerelease: true, body: MARKER, immutable: true }]) assert.throws(() => validateExistingRelease(release), /Refusing/)
})

test('outdated build skips before changing any release', async () => {
  const state = server({ staleAt: 1 })
  assert.equal((await execute(state)).skipped, true)
  assert.equal(state.calls.length, 1)
})

test('upload failure retains old assets and cleans only newly uploaded files', async () => {
  const state = server({ failUpload: 2 })
  await assert.rejects(execute(state), /Upload failed/)
  assert.deepEqual(state.calls.filter(row => row.method === 'DELETE').map(row => row.route), ['/releases/assets/101'])
  assert.ok(!state.calls.some(row => row.method === 'PATCH'))
})

test('successful promotion follows uploads, is a regular latest Desktop Preview and preserves manual attachments', async () => {
  const state = server()
  assert.equal((await execute(state)).skipped, false)
  const promotion = state.calls.findIndex(row => row.route === '/releases/1' && row.method === 'PATCH')
  assert.ok(promotion > state.calls.findLastIndex(row => row.route.startsWith('https://uploads.github.com/')))
  assert.equal(state.calls[promotion].body.make_latest, 'true')
  assert.equal(state.calls[promotion].body.prerelease, false)
  assert.ok(state.calls[promotion].body.body.includes(SHA.slice(0, 12)))
  assert.deepEqual(state.calls.filter(row => row.method === 'DELETE').map(row => row.route), ['/releases/assets/9'])
})

test('push arriving during upload does not promote stale downloads', async () => {
  const state = server({ staleAt: 2 })
  assert.equal((await execute(state)).skipped, true)
  assert.equal(state.calls.filter(row => row.method === 'DELETE').length, 2)
  assert.ok(!state.calls.some(row => row.method === 'PATCH'))
})

test('failed metadata update restores tag and keeps previous downloads', async () => {
  const state = server({ failPromotion: true })
  await assert.rejects(execute(state), /Metadata failed/)
  const tags = state.calls.filter(row => row.route === '/git/refs/tags/development-preview')
  assert.deepEqual(tags.map(row => row.body.sha), [SHA, OTHER])
  assert.ok(!state.calls.some(row => row.route === '/releases/assets/9'))
})

test('lost successful publication response is reconciled, not rolled back', async () => {
  const state = server({ lostPromotionResponse: true })
  assert.equal((await execute(state)).skipped, false)
  assert.ok(!state.calls.some(row => row.route === '/releases/assets/101' || row.route === '/releases/assets/102'))
})

test('interrupted first-run draft is found instead of creating a duplicate', async () => {
  const calls = []
  const result = await findPreviewRelease(async route => {
    calls.push(route)
    if (route.includes('/tags/')) throw Object.assign(new Error('Not published'), { status: 404 })
    return [{ id: 5, tag_name: 'development-preview', draft: true, prerelease: true, body: MARKER }]
  })
  assert.equal(result.id, 5)
  assert.equal(calls.length, 2)
})

test('first preview stays draft until uploads complete, then creates its lightweight tag', async () => {
  const state = server()
  const created = []
  const base = state.api
  state.api = async (route, options = {}) => {
    if (route === '/releases/tags/development-preview' || route === '/git/ref/tags/development-preview') {
      throw Object.assign(new Error('Missing'), { status: 404 })
    }
    if (route === '/releases?per_page=100&page=1') return []
    if (route === '/releases' && options.method === 'POST') {
      created.push(options.body)
      return { id: 1, prerelease: true, draft: true, body: MARKER,
        upload_url: 'https://uploads.github.com/release/1/assets{?name,label}' }
    }
    if (route === '/git/refs' && options.method === 'POST') { created.push(options.body); return {} }
    return base(route, options)
  }
  assert.equal((await execute(state)).skipped, false)
  assert.equal(created[0].draft, true)
  assert.equal(created[0].prerelease, false)
  assert.deepEqual(created[1], { ref: 'refs/tags/development-preview', sha: SHA })
})

test('workflow gates publishing on all builds, main, and a job-local write token', async () => {
  const workflow = await readFile(new URL('../../.github/workflows/build.yml', import.meta.url), 'utf8')
  assert.match(workflow, /branches: \[main\]/)
  assert.match(workflow, /needs: \[source, build\]/)
  assert.match(workflow, /build:\s+needs: source/)
  assert.match(workflow, /run: npm ci --dry-run --ignore-scripts --no-audit --no-fund/)
  assert.match(workflow, /if: github\.ref == 'refs\/heads\/main'/)
  assert.match(workflow, /cancel-in-progress: false/)
  assert.equal((workflow.match(/contents: write/g) ?? []).length, 1)
  assert.match(workflow, /pattern: ReflowStudio-\*/)
  for (const target of ['windows-x64', 'linux-x64', 'macos-arm64', 'macos-x64']) {
    assert.ok(workflow.includes(`target: ${target}`))
  }
})


test('release notes identify desktop preview scope and include supplied commit changes', () => {
  const body = releaseBody('owner/repo', SHA, '123', '## Recent changes\n- Fix recovery')
  assert.match(body, /Desktop Preview/)
  assert.match(body, /regular GitHub release/)
  assert.match(body, /Fix recovery/)
  assert.doesNotMatch(body, /Pre-release for volunteer/)
})
