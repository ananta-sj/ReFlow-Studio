import type { DeletionPreview, DeletionResult } from './api'

export function describeDeletion(preview: DeletionPreview): string {
  const lines = [`${preview.files ?? 0} files (${((preview.bytes ?? 0) / 1_000_000).toFixed(2)} MB) will be permanently deleted.`]
  for (const item of preview.candidates ?? []) {
    lines.push(`${item.path}: ${item.files} files, ${(item.bytes / 1_000_000).toFixed(2)} MB`)
  }
  for (const item of preview.retained ?? []) lines.push(`Kept: ${item.path}. ${item.reason}`)
  return lines.join('\n')
}

export function describeDeletionResult(result: DeletionResult): string {
  return [result.message, ...(result.removed ?? []).map((path) => `Processed: ${path}`),
    ...(result.remaining ?? []).map((path) => `Remaining: ${path}`),
    ...(result.retained ?? []).map((item) => `Kept: ${item.path}. ${item.reason}`)]
    .filter(Boolean).join('\n') || 'The operation could not finish. Review the files again.'
}
