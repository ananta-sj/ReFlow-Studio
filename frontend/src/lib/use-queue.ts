import { bridge } from './api'
import { confirmAction } from './use-confirm'
import { runJobAction, useJobs } from './use-jobs'

async function report(send: Parameters<typeof runJobAction>[0]) {
  const result = await runJobAction(send)
  if (!result.ok) await confirmAction({ title: 'Queue action unavailable', description: result.message ?? 'Try again after the active job finishes.', alertOnly: true })
  return result
}
export function addToQueue(paths: string[]) { return report(() => bridge.addQueueDrafts(paths)) }
export function removeFromQueue(id: string) { return report(() => bridge.removeQueueItem(id)) }
export function pauseQueue() { return report(() => bridge.setQueuePaused(true)) }
export function resumeQueue() { return report(bridge.resumeQueueBatch) }
export function clearQueueHistory() { return report(bridge.clearCompletedQueue) }
export function useQueue() { return useJobs().queue.filter((job) => job.status === 'draft' || job.status === 'queued') }
