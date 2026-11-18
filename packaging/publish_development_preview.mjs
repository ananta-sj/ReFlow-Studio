/** Publish only verified desktop candidates; no third-party Node dependencies. */
import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { lstat, readdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const VERSION_SERIES = '0.7'
export const MARKER = '<!-- reflow-development-preview:v1 -->'
export const PACKAGES = Object.freeze({
  'windows-x64': 'ReflowStudio-windows-x64-desktop-preview.zip',
  'linux-x64': 'ReflowStudio-linux-x64-desktop-preview.tar.gz',
  'macos-arm64': 'ReflowStudio-macos-arm64-desktop-preview.tar.gz',
  'macos-x64': 'ReflowStudio-macos-x64-desktop-preview.tar.gz',
  source: 'ReflowStudio-source.zip',
})

export async function hash(file) {
  const digest = createHash('sha256')
  for await (const block of createReadStream(file)) digest.update(block)
  return digest.digest('hex')
}

export async function collectAssets(folder, sha, runId, attempt) {
  if (!/^[a-f0-9]{40}$/.test(sha) || !/^\d+$/.test(runId) || !/^\d+$/.test(attempt)) {
    throw new Error('Invalid build identity')
  }
  const expected = Object.values(PACKAGES).flatMap(name => [name, `${name}.sha256`])
  const actual = await readdir(folder)
  if (actual.length !== expected.length || actual.some(name => !expected.includes(name))) {
    throw new Error('Expected exactly four platform packages, source, and their checksums')
  }
  const assets = []
  for (const [target, original] of Object.entries(PACKAGES)) {
    const file = path.join(folder, original)
    const stat = await lstat(file)
    const sidecar = path.join(folder, `${original}.sha256`)
    if (!stat.isFile() || stat.isSymbolicLink() || !stat.size || stat.size >= 2 * 1024 ** 3 ||
        !(await lstat(sidecar)).isFile() || (await lstat(sidecar)).isSymbolicLink()) {
      throw new Error(`Invalid package or checksum: ${original}`)
    }
    const checksum = (await readFile(sidecar, 'utf8')).trim()
    const match = checksum.match(/^([a-f0-9]{64}) {2}([^\r\n]+)$/)
    const digest = await hash(file)
    if (!match || match[2] !== original || match[1] !== digest) {
      throw new Error(`Checksum mismatch: ${original}`)
    }
    const extension = original.endsWith('.tar.gz') ? '.tar.gz' : '.zip'
    assets.push({ target, file, bytes: stat.size, sha256: digest,
      name: `ReflowStudio-dev-${target}-${sha.slice(0, 12)}-r${runId}-a${attempt}${extension}` })
  }
  return assets
}

export function releaseBody(repository, sha, runId, changes = '') {
  return `${MARKER}\n# ReFlow Studio - Desktop Preview\n\n` +
    `Automatically built from [\`${sha.slice(0, 12)}\`](https://github.com/${repository}/commit/${sha}).\n` +
    `[Build checks and dependency inventories](https://github.com/${repository}/actions/runs/${runId}).\n\n` +
    '**Desktop Preview for volunteer testing. Published as a regular GitHub release.**\n\n' +
    'Choose `windows-x64`, `linux-x64`, `macos-arm64` (Apple Silicon), or `macos-x64` (Intel). ' +
    'Extract the entire package; keep its companion files together. The `source` ZIP contains source code.\n\n' +
    '**Scope:** desktop application and Python only. AI engine environments, model weights, voices, ' +
    'credentials and FFmpeg/FFprobe are not bundled. Windows requires WebView2/Visual C++ runtimes. ' +
    'macOS builds are not Developer ID signed or notarized. Full engine/fresh-machine validation is ongoing.\n\n' +
    'Original ReFlow code is AGPL-3.0-only. Download the matching source ZIP alongside these packages. ' +
    'Third-party components and models retain their own terms. See LICENSING.md in the source/package.\n\n' +
    'Reliable unattended multi-character episode/movie dubbing remains unvalidated. Build/smoke checks ' +
    'do not verify translation meaning, natural acting or complete episode quality. Component licensing ' +
    'review remains pending; these are development testing packages.\n\n' +
    `${changes}\n**Current download set:** filenames containing \`${sha.slice(0, 12)}-r${runId}-\`. ` +
    'Use the matching SHA256SUMS and manifest. During an upload, additional files from a pending build ' +
    'may appear; use only the set identified here. Earlier preview releases and their downloads are preserved.\n\n' +
    'Report your OS/architecture, filename, engine setup and reproduction steps in ' +
    `[Issues](https://github.com/${repository}/issues), without credentials or private media.\n`
}

export function validateExistingRelease(release) {
  if (release && (!release.body?.includes(MARKER) || release.immutable)) {
    throw new Error('Refusing to replace an unowned or immutable release')
  }
}

class GitHubError extends Error {
  constructor(status, message) { super(message); this.status = status }
}

export function apiClient(repository, token) {
  return async function api(route, { method = 'GET', body, file } = {}) {
    const upload = route.startsWith('https://uploads.github.com/')
    if (route.startsWith('https:') && !upload) throw new Error('Unexpected upload host')
    const url = upload ? route : `https://api.github.com/repos/${repository}${route}`
    const headers = { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'ReFlow-development-preview' }
    let data
    if (file) {
      headers['Content-Type'] = 'application/octet-stream'
      headers['Content-Length'] = String((await lstat(file)).size)
      data = createReadStream(file)
    } else if (body !== undefined) {
      headers['Content-Type'] = 'application/json'; data = JSON.stringify(body)
    }
    const response = await fetch(url, { method, headers, body: data,
      ...(file ? { duplex: 'half' } : {}), signal: AbortSignal.timeout(file ? 600_000 : 60_000) })
    if (!response.ok) {
      // Do not print response bodies or request headers containing account data.
      throw new GitHubError(response.status, `GitHub ${method} failed: HTTP ${response.status}`)
    }
    return response.status === 204 ? null : response.json()
  }
}

async function optional(api, route) {
  try { return await api(route) } catch (error) { if (error.status === 404) return null; throw error }
}

async function listRecords(api, route) {
  const rows = []
  for (let page = 1; ; page++) {
    const batch = await api(`${route}?per_page=100&page=${page}`)
    rows.push(...batch)
    if (batch.length < 100) return rows
  }
}

export function nextPreviewTag(tags) {
  const prefix = `v${VERSION_SERIES}.`
  let patch = 0
  for (const tag of tags) {
    if (!tag?.startsWith(prefix)) continue
    const match = tag.slice(prefix.length).match(/^(0|[1-9]\d*)(?:-[a-zA-Z0-9.-]+)?$/)
    if (!match) continue
    const value = Number(match[1])
    if (!Number.isSafeInteger(value) || value >= Number.MAX_SAFE_INTEGER) throw new Error('Preview version exceeds safe range')
    patch = Math.max(patch, value)
  }
  return `${prefix}${patch + 1}-desktop-preview`
}

function buildIdentity(runId, attempt, sha) {
  if (!/^\d+$/.test(runId) || !/^\d+$/.test(attempt) || !/^[a-f0-9]{40}$/.test(sha)) {
    throw new Error('Invalid build identity')
  }
  return `<!-- reflow-preview-build:${runId}:${attempt}:${sha} -->`
}

export function findPreviewRelease(releases, runId, attempt, sha) {
  const identity = buildIdentity(runId, attempt, sha)
  return releases.find(row => row.body?.includes(MARKER) && row.body.includes(identity))
}

/** Serialized by the workflow. Every build owns a separate versioned release. */
export async function publish({ api, repository, sha, runId, attempt = '1', assets, changes = '' }) {
  const identity = buildIdentity(runId, attempt, sha)
  const head = () => api('/git/ref/heads/main')
  if ((await head()).object.sha !== sha) return { skipped: true, reason: 'Newer main commit exists' }
  const releases = await listRecords(api, '/releases')
  let release = findPreviewRelease(releases, runId, attempt, sha)
  if (release && !/^v0\.7\.[1-9]\d*-desktop-preview$/.test(release.tag_name)) {
    throw new Error('Build identity is attached to an unexpected release tag')
  }
  if (release && !release.draft) return { skipped: false, tag: release.tag_name, alreadyPublished: true }
  validateExistingRelease(release)
  if (!release) {
    const tags = await listRecords(api, '/tags')
    const tag = nextPreviewTag([...tags.map(row => row.name), ...releases.map(row => row.tag_name)])
    release = await api('/releases', { method: 'POST', body: {
      tag_name: tag, target_commitish: sha, name: `ReFlow Studio ${tag.replace('-desktop-preview', '')} - Desktop Preview`,
      draft: true, prerelease: false,
      body: `${MARKER}\n${identity}\nPreparing this desktop preview.` } })
  }
  const tag = release.tag_name
  const oldAssets = await listRecords(api, `/releases/${release.id}/assets`)
  const uploaded = []
  let promoted = false
  let tagCreated = false
  let promotionUncertain = false
  try {
    const existing = new Map(oldAssets.map(asset => [asset.name, asset]))
    for (const asset of assets) {
      const previous = existing.get(asset.name)
      if (previous) {
        if (previous.state === 'uploaded' && previous.size === asset.bytes &&
            previous.digest === `sha256:${asset.sha256}`) continue
        // This exact build owns the unpublished draft. Replace only an expected
        // artifact whose integrity cannot be verified; preserve unrelated files.
        await api(`/releases/assets/${previous.id}`, { method: 'DELETE' })
      }
      const url = release.upload_url.replace(/\{.*$/, '') + '?name=' + encodeURIComponent(asset.name)
      const result = await api(url, { method: 'POST', file: asset.file })
      uploaded.push(result)
      if (result.state !== 'uploaded' || result.size !== asset.bytes ||
          (result.digest && result.digest !== `sha256:${asset.sha256}`)) {
        throw new Error(`Upload integrity check failed: ${asset.name}`)
      }
    }
    if ((await head()).object.sha !== sha) return { skipped: true, reason: 'Newer main commit exists' }
    const existingTag = await optional(api, `/git/ref/tags/${tag}`)
    if (existingTag && (existingTag.object.type !== 'commit' || existingTag.object.sha !== sha)) {
      throw new Error('Version tag already belongs to another commit; refusing to move it')
    }
    if (!existingTag) {
      await api('/git/refs', { method: 'POST', body: { ref: `refs/tags/${tag}`, sha } })
      tagCreated = true
    }
    const publication = { tag_name: tag,
      name: `ReFlow Studio ${tag.replace('-desktop-preview', '')} - Desktop Preview`, draft: false,
      prerelease: false, make_latest: 'true',
      body: releaseBody(repository, sha, runId, changes).replace(MARKER, `${MARKER}\n${identity}`) }
    try {
      await api(`/releases/${release.id}`, { method: 'PATCH', body: publication })
      promoted = true
    } catch (error) {
      let observed
      try { observed = await api(`/releases/${release.id}`) }
      catch {
        promotionUncertain = true
        console.warn('Cannot confirm publication. Keeping this build for maintainer inspection.')
        throw error
      }
      if (observed.body === publication.body && !observed.draft && observed.prerelease === false) promoted = true
      else {
        promotionUncertain = !observed.draft
        throw error
      }
    }
    return { skipped: false, tag }
  } finally {
    if (!promoted && !promotionUncertain) {
      if (tagCreated) {
        try {
          const current = await optional(api, `/git/ref/tags/${tag}`)
          if (current?.object.type === 'commit' && current.object.sha === sha) {
            await api(`/git/refs/tags/${tag}`, { method: 'DELETE' })
          }
        } catch { console.warn('Unpublished version tag cleanup needs maintainer attention.') }
      }
      for (const asset of uploaded) {
        try { await api(`/releases/assets/${asset.id}`, { method: 'DELETE' }) }
        catch { console.warn('An unpromoted upload needs maintainer cleanup.') }
      }
    }
  }
}

async function main() {
  const { GITHUB_REPOSITORY: repository, GITHUB_SHA: sha, GITHUB_RUN_ID: runId,
    GITHUB_RUN_ATTEMPT: attempt, GH_TOKEN: token, GITHUB_REF: ref } = process.env
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository ?? '') || !token || ref !== 'refs/heads/main') {
    throw new Error('Publishing requires an authenticated main-branch workflow')
  }
  const folder = path.resolve(process.argv[2] ?? 'preview-downloads')
  const assets = await collectAssets(folder, sha, runId, attempt)
  const stamp = `${sha.slice(0, 12)}-r${runId}-a${attempt}`
  const manifest = path.join(folder, `ReflowStudio-dev-manifest-${stamp}.json`)
  await writeFile(manifest, JSON.stringify({ commit: sha, run_id: runId, attempt,
    scope: 'desktop-preview', episode_dubbing_validated: false, ai_engines_bundled: false,
    files: assets.map(({ file, ...record }) => record) }, null, 2) + '\n')
  assets.push({ name: path.basename(manifest), file: manifest, bytes: (await lstat(manifest)).size, sha256: await hash(manifest) })
  const checksums = path.join(folder, `ReflowStudio-dev-SHA256SUMS-${stamp}.txt`)
  await writeFile(checksums, assets.map(row => `${row.sha256}  ${row.name}\n`).join(''))
  assets.push({ name: path.basename(checksums), file: checksums, bytes: (await lstat(checksums)).size, sha256: await hash(checksums) })
  const api = apiClient(repository, token)
  const commits = await api(`/commits?sha=${sha}&per_page=10`)
  const changes = '## Recent changes\n\n' + commits.map(commit => {
    const subject = commit.commit.message.split(/\r?\n/)[0].replace(/[\r\n]/g, ' ')
    return `- ${subject} ([${commit.sha.slice(0, 12)}](https://github.com/${repository}/commit/${commit.sha}))`
  }).join('\n') + '\n'
  const result = await publish({ api, repository, sha, runId, attempt, assets, changes })
  console.log(JSON.stringify(result))
  if (process.env.GITHUB_STEP_SUMMARY) {
    const summary = result.skipped ? `Preview not published: ${result.reason}.\n` :
      `Desktop Preview published: https://github.com/${repository}/releases/tag/${result.tag}\n\nCommit: ${sha}\n`;
    await writeFile(process.env.GITHUB_STEP_SUMMARY, summary, { flag: 'a' })
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1 })
}
