// Catalog metadata is untrusted. Never allow script, file or custom-protocol
// navigation from a page that has access to the desktop bridge.
export function safeExternalUrl(value: string | undefined): string | undefined {
  if (!value || [...value].some(char => char.charCodeAt(0) <= 32 || char.charCodeAt(0) === 127 || char === '\\')) return undefined
  try {
    const url = new URL(value)
    if (!['https:', 'http:'].includes(url.protocol) || !url.hostname || url.username || url.password) return undefined
    return url.href
  } catch {
    return undefined
  }
}
