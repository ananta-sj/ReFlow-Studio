import type { DownloadFailure } from './api'
const messages: Record<string, string> = {
  interrupted: 'The previous download was interrupted when ReFlow closed. Retry to start a new transfer; existing files are kept.',
  missing_transport: 'Repository downloads need the desktop Hub download client. Update the desktop setup, then retry.',
  access_denied: 'Repository access was denied. Check model access and your local sign-in before retrying.',
  network_error: 'The transfer could not reach the server. Check the connection and retry.',
  storage_error: 'The transfer could not write its files. Check free space and folder permissions before retrying.',
  transfer_failed: 'The model transfer did not finish. Retained files are preserved; retry or review the local diagnostics.',
}
export function readDownloadFailure(value: unknown): DownloadFailure {
  const code = value && typeof value === 'object' && 'code' in value &&
    typeof value.code === 'string' && Object.hasOwn(messages, value.code) ? value.code : 'transfer_failed'
  return { code, message: messages[code] }
}
