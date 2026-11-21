/** Publish only verified desktop candidates; no third-party Node dependencies. */
import { createHash } from 'node:crypto'
import { constants } from 'node:fs'
import { lstat, open, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const VERSION_SERIES = '0.7'
export const MARKER = '<!-- reflow-development-preview:v1 -->'
export const PACKAGES = Object.freeze({
  'windows-x64': 'ReflowStudio-windows-x64-desktop-preview.zip',
  'linux-x64': 'ReflowStudio-linux-x64-desktop-preview.tar.gz',
  'macos-arm64': 'ReflowStudio-macos-arm64-desktop-preview.tar.gz',
  'macos-x64': 'ReflowStudio-macos-x64-desktop-preview.tar.gz',
  'windows-x64-setup': 'ReflowStudio-windows-x64-desktop-preview-setup.exe',
  'linux-x64-setup': 'ReflowStudio-linux-x64-desktop-preview-setup.run',
  'macos-arm64-setup': 'ReflowStudio-macos-arm64-desktop-preview-setup.dmg',
  'macos-x64-setup': 'ReflowStudio-macos-x64-desktop-preview-setup.dmg',
  source: 'ReflowStudio-source.zip',
})

export async function openRegularFile(file, maximumBytes = 2 * 1024 ** 3) {
  const handle = await open(file, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0))
  try {
    // Validate the opened object, then read that same descriptor. The path is
    // checked afterward only to reject links on platforms without O_NOFOLLOW.
    const stat = await handle.stat()
    const entry = await lstat(file)
    if (!stat.isFile() || !entry.isFile() || entry.isSymbolicLink() ||
        entry.dev !== stat.dev || entry.ino !== stat.ino ||
        !stat.size || stat.size >= maximumBytes) {
      throw new Error(`Invalid package or checksum: ${path.basename(file)}`)
    }
    return handle
  } catch (error) {
    await handle.close()
    throw error
  }
}

async function hashHandle(handle) {
  const digest = createHash('sha256')
  for await (const block of handle.createReadStream({ autoClose: false })) digest.update(block)
  return digest.digest('hex')
}

export async function hash(file) {
  const handle = await openRegularFile(file)
  try { return await hashHandle(handle) } finally { await handle.close() }
}

export async function collectAssets(folder, sha, runId, attempt) {
  if (!/^[a-f0-9]{40}$/.test(sha) || !/^\d+$/.test(runId) || !/^\d+$/.test(attempt)) {
    throw new Error('Invalid build identity')
  }
  const expected = Object.values(PACKAGES).flatMap(name => [name, `${name}.sha256`])
  const actual = await readdir(folder)
  if (actual.length !== expected.length || actual.some(name => !expected.includes(name))) {
    throw new Error('Expected exactly four platform packages, four installers, source, and their checksums')
  }
  const assets = []
  for (const [target, original] of Object.entries(PACKAGES)) {
    const file = path.join(folder, original)
    const sidecar = path.join(folder, `${original}.sha256`)
    const packageHandle = await openRegularFile(file)
    let stat, digest, checksum
    try {
      stat = await packageHandle.stat()
      const checksumHandle = await openRegularFile(sidecar, 1024)
      try {
        const buffer = Buffer.alloc(1024)
        const { bytesRead } = await checksumHandle.read(buffer, 0, buffer.length, 0)
        if (bytesRead === buffer.length) throw new Error(`Invalid package or checksum: ${original}`)
        checksum = buffer.subarray(0, bytesRead).toString('utf8').trim()
      }
      finally { await checksumHandle.close() }
      digest = await hashHandle(packageHandle)
    } finally { await packageHandle.close() }
    const match = checksum.match(/^([a-f0-9]{64}) {2}([^\r\n]+)$/)
    if (!match || match[2] !== original || match[1] !== digest) {
      throw new Error(`Checksum mismatch: ${original}`)
    }
    const extension = original.endsWith('.tar.gz') ? '.tar.gz' : path.extname(original)
    assets.push({ target, file, bytes: stat.size, sha256: digest,
      name: `ReflowStudio-dev-${target}-${sha.slice(0, 12)}-r${runId}-a${attempt}${extension}` })
  }
  return assets
}

function plainText(value) {
  return String(value).replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c])
    .replace(/@/g, '&#64;').replace(/[\\`*_{}\[\]()#!|]/g, c => `\\${c}`).replace(/[\r\n]/g, ' ')
}

export function formatChanges(repository, commits, comparison = '') {
  const groups = new Map()
  for (const row of commits.slice(-30)) {
    if (!/^[a-f0-9]{40}$/.test(row.sha)) throw new Error('Invalid change commit')
    const subject = row.commit.message.split(/\r?\n/)[0].slice(0, 240)
    const category = /^(security|sec)(?:[(:!]|\s)/i.test(subject) ? 'Security' :
      /^fix(?:[(:!]|\s)/i.test(subject) ? 'Fixes' : /^feat(?:[(:!]|\s)/i.test(subject) ? 'Features' :
      /^(docs|ci|build|test|chore)(?:[(:!]|\s)/i.test(subject) ? 'Maintenance and documentation' : 'Updates'
    if (!groups.has(category)) groups.set(category, [])
    groups.get(category).push(`- ${plainText(subject)} ([${row.sha.slice(0, 8)}](https://github.com/${repository}/commit/${row.sha}))`)
  }
  return '## What changed\n\n' + [...groups].map(([name, rows]) => `### ${name}\n\n${rows.join('\n')}\n`).join('\n') +
    (comparison ? `\n[Full comparison](${comparison}).\n` : '\nInitial preview history; no earlier owned preview was found.\n') +
    (commits.length > 30 ? '\nShowing the latest 30 returned commits; use the comparison for the complete history.\n' : '')
}

export async function changeNotes(api, repository, sha) {
  const releases = await listRecords(api, '/releases')
  const previous = releases.find(r => !r.draft && r.body?.includes(MARKER) &&
    /^v0\.7\.[1-9]\d*-desktop-preview$/.test(r.tag_name) && r.target_commitish !== sha)
  if (!previous) return formatChanges(repository, await api(`/commits?sha=${sha}&per_page=30`))
  const base = encodeURIComponent(previous.tag_name)
  const result = await api(`/compare/${base}...${sha}?per_page=100`)
  if (!['ahead', 'identical'].includes(result.status)) throw new Error('Previous preview is not an ancestor of this build')
  let commits = result.commits
  if (result.total_commits > 100) {
    const lastPage = Math.ceil(result.total_commits / 100)
    commits = (await api(`/compare/${base}...${sha}?per_page=100&page=${lastPage}`)).commits
    if (commits.length < 30) {
      const preceding = await api(`/compare/${base}...${sha}?per_page=100&page=${lastPage - 1}`)
      commits = [...preceding.commits, ...commits]
    }
  }
  return formatChanges(repository, commits, `https://github.com/${repository}/compare/${base}...${sha}`) +
    (result.total_commits > commits.length ? '\nThe comparison contains additional commits beyond this summary.\n' : '')
}

export function releaseBody(repository, sha, runId, changes = '', assets = [], tag = '') {
  const labels = { 'linux-x64-setup': 'Linux (x64) per-user installer', 'macos-arm64-setup': 'macOS (Apple Silicon) disk image', 'macos-x64-setup': 'macOS (Intel) disk image', 'windows-x64-setup': 'Windows (x64) installer', 'windows-x64': 'Windows (x64) portable', 'linux-x64': 'Linux (x64)',
    'macos-arm64': 'macOS (Apple Silicon)', 'macos-x64': 'macOS (Intel)', source: 'Source code' }
  const downloads = assets.filter(row => labels[row.target]).map(row =>
    `| ${labels[row.target]} | [Download](https://github.com/${repository}/releases/download/${encodeURIComponent(tag)}/${encodeURIComponent(row.name)}) | ${(row.bytes / 1048576).toFixed(1)} MB |`).join('\n')
  return `${MARKER}\n# ReFlow Studio · Desktop Preview\n\n` +
    '**Desktop Preview for volunteer testing. Published as a regular GitHub release.**\n\n' +
    `${changes}\n## Downloads\n\n` +
    (downloads ? `| Platform | Package | Size |\n| --- | --- | ---: |\n${downloads}\n\n` : 'Choose the package matching your operating system and architecture from Assets below.\n\n') +
    '### Getting started\n\n' +
    '1. On Windows, run the **installer** for a per-user installation, or extract the **entire portable ZIP**. On Linux, use the `.run` per-user installer or portable archive. On macOS, mount the matching DMG and run **Install Reflow Studio.command**, then open the installed app in `~/Applications`. Keep portable companion files together.\n' +
    '2. Follow the [setup guide](https://github.com/' + repository + '/blob/' + sha + '/docs/GITHUB_NATIVE_BUILDS.md) for launch instructions and prerequisites.\n' +
    '3. Configure supported engines and models before attempting a dub. Start with a short clip.\n\n' +
    '### Verify your download\n\nUse the matching `SHA256SUMS` and manifest in Assets to check package integrity and build identity.\n\n' +
    '<details>\n<summary>Preview scope and known limitations</summary>\n\n' +
    'AI engine environments, model weights, voices, credentials and FFmpeg/FFprobe are **not bundled**. ' +
    'Windows requires WebView2/Visual C++ runtimes; the installer does not download prerequisites. Windows packages are unsigned and may trigger reputation warnings. Uninstall preserves generated settings, models and outputs. macOS builds are not Developer ID signed or notarized. ' +
    'Full engine/fresh-machine validation is ongoing. Reliable unattended multi-character episode/movie dubbing remains unvalidated. ' +
    'Build/smoke checks do not verify translation meaning, natural acting or complete episode quality. ' +
    'Component licensing review remains pending; these are development testing packages.\n\n' +
    'Original ReFlow code is AGPL-3.0-only. Download the matching source ZIP. Third-party components and models retain their own terms; see LICENSING.md.\n\n</details>\n\n' +
    '## Testing and feedback\n\nReport your OS, architecture, package filename, engine setup and reproduction steps in ' +
    `[Issues](https://github.com/${repository}/issues). Do not upload credentials or private media. ` +
    `[Security reporting policy](https://github.com/${repository}/blob/${sha}/.github/SECURITY.md).\n\n` +
    `**Build:** [\`${sha.slice(0, 12)}\`](https://github.com/${repository}/commit/${sha}) · ` +
    `[Checks and dependency inventories](https://github.com/${repository}/actions/runs/${runId}).\n\n` +
    `**Current download set:** filenames containing \`${sha.slice(0, 12)}-r${runId}-\`. ` +
    'Earlier preview releases and their downloads are preserved.\n'
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
    let data, uploadHandle, response
    try {
      if (file) {
        headers['Content-Type'] = 'application/octet-stream'
        uploadHandle = await openRegularFile(file)
        headers['Content-Length'] = String((await uploadHandle.stat()).size)
        data = uploadHandle.createReadStream({ autoClose: false })
      } else if (body !== undefined) {
        headers['Content-Type'] = 'application/json'; data = JSON.stringify(body)
      }
      response = await fetch(url, { method, headers, body: data,
        ...(file ? { duplex: 'half' } : {}), signal: AbortSignal.timeout(file ? 600_000 : 60_000) })
    } finally {
      if (data?.destroy) data.destroy()
      if (uploadHandle) await uploadHandle.close()
    }
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
      body: releaseBody(repository, sha, runId, changes, assets, tag).replace(MARKER, `${MARKER}\n${identity}`) }
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
  const changes = await changeNotes(api, repository, sha)
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
