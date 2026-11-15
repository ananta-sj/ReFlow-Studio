import { useEffect, useState } from 'react'
import { bridge, type PipelineTemplateId, type RenderParams } from './api'
import { runJobAction, useJobs } from './use-jobs'
import { confirmAction } from './use-confirm'

const STILL_WORKING_THRESHOLD_MS = 45_000
export function useRenderJob() {
  const session = useJobs()
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 5000)
    return () => clearInterval(timer)
  }, [])
  function start(inputPath: string, params: Partial<RenderParams>, templateId: PipelineTemplateId = 'video_dub') {
    return runJobAction(() => bridge.startRender(inputPath, params, templateId))
  }
  function startBatch(params: Partial<RenderParams>, templateId: PipelineTemplateId = 'video_dub', expectedIds?: string[]) {
    return runJobAction(() => bridge.startQueueBatch(params, templateId, expectedIds))
  }
  async function stop() {
    const result = await runJobAction(bridge.stopRender)
    if (!result.ok) await confirmAction({ title: 'Stop unavailable', description: result.message ?? 'Unable to request cancellation.', alertOnly: true })
    return result
  }
  async function retry() {
    const result = await runJobAction(() => bridge.retryRender())
    if (!result.ok) await confirmAction({ title: 'Retry unavailable', description: result.message ?? 'Unable to retry this job.', alertOnly: true })
    return result
  }
  return { ...session.render, start, startBatch, stop, retry, isRunning: session.busy,
    isStopping: session.render.status === 'stopping',
    waitingSeconds: session.busy && session.render.status === 'running' && now - session.lastEventAt >= STILL_WORKING_THRESHOLD_MS
      ? Math.floor((now - session.lastEventAt) / 1000) : null }
}
