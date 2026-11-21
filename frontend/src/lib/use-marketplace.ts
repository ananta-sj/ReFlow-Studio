import { confirmAction } from "./use-confirm"
import { describeDeletion, describeDeletionResult } from './deletion-preview'
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { subscribe } from "@/lib/events"
import { bridge, type ModelDownloadProgress, type ModelEntry, type StageType } from "@/lib/api"

export function useMarketplace(stageType: StageType) {
  const [models, setModels] = useState<ModelEntry[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [progress, setProgress] = useState<Record<string, ModelDownloadProgress>>({})

  const records = useRef<ModelEntry[]>([])
  const session = useMemo(() => ({ stageType, revision: 0, alive: true }), [stageType])
  const pending = useRef(new Set<string>())
  const [retrying, setRetrying] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const refresh = useCallback(async () => {
    if (!session.alive) return
    const own = ++session.revision
    try {
      const [list, activeMap] = await Promise.all([bridge.listModels(stageType), bridge.getActiveModels()])
      if (!session.alive || own !== session.revision) return
      records.current = list
      setModels(list); setActiveId(activeMap[stageType]?.id ?? null); setLoadError(null)
    } catch {
      if (session.alive && own === session.revision) setLoadError('Model connections could not refresh. Reopen this category to retry.')
    }
  }, [stageType, session])

  useEffect(() => {
    session.alive = true
    records.current = []
    setProgress({})
    void refresh()
    return () => { session.alive = false; session.revision++ }
  }, [refresh, session])

  useEffect(() => {
    const currentEvent = (payload: unknown) => {
      if (!payload || typeof payload !== 'object' || !('modelId' in payload)) return false
      const event = payload as { modelId: string; attemptId?: string }
      const model = records.current.find(row => row.id === event.modelId)
      if (!model) { void refresh(); return false }
      const expected = model.meta?.download_attempt_id
      return typeof expected === 'string' ? expected === event.attemptId : !event.attemptId
    }
    const terminal = (payload: unknown) => {
      if (!currentEvent(payload)) { void refresh(); return }
      const { modelId } = payload as { modelId: string }
      setProgress(prev => { const next = { ...prev }; delete next[modelId]; return next })
      void refresh()
    }
    const unsubs = [
      subscribe('model_download_progress', payload => {
        if (!currentEvent(payload)) return
        const p = payload as ModelDownloadProgress
        if (records.current.find(row => row.id === p.modelId)?.status !== 'downloading') return
        setProgress(prev => ({ ...prev, [p.modelId]: p }))
      }),
      subscribe('model_installed', terminal),
      subscribe('model_download_stopping', () => { void refresh() }),
      subscribe('model_download_finished', terminal),
      subscribe('model_download_error', terminal),
    ]
    return () => unsubs.forEach(fn => fn())
  }, [refresh])

  async function retry(modelId: string) {
    if (pending.current.has(modelId)) return { ok: false, message: 'That retry is already starting.' }
    pending.current.add(modelId); setRetrying([...pending.current])
    try {
      const result = await bridge.retryModelDownload(modelId)
      if (result.ok && result.model && session.alive) {
        records.current = records.current.map(row => row.id === modelId ? result.model! : row)
        setModels(records.current)
      }
      if (!result.ok) await confirmAction({ title: 'Retry unavailable', description: result.message ?? 'This download could not be retried.', alertOnly: true })
      await refresh()
      return result
    } catch {
      await confirmAction({ title: 'Retry unavailable', description: 'The desktop connection could not start a retry. Reopen this category and try again.', alertOnly: true })
      return { ok: false }
    } finally {
      pending.current.delete(modelId)
      if (session.alive) setRetrying([...pending.current])
    }
  }

  async function setActive(modelId: string) {
    const result = await bridge.setActiveModel(stageType, modelId)
    if (result.ok) setActiveId(modelId)
    else await confirmAction({ title: 'Model selection unavailable', description: result.message ?? 'This model could not be selected.', alertOnly: true })
    return result
  }

  async function cancel(modelId: string) {
    const result = await bridge.cancelModelDownload(modelId)
    if (!result.ok) await confirmAction({ title: "Stop unavailable", description: result.message ?? "The download could not be stopped.", alertOnly: true })
    await refresh()
  }

  async function remove(modelId: string) {
    const preview = await bridge.previewModelRemoval(modelId)
    if (!preview.ok || !preview.token) {
      await confirmAction({ title: "Model removal unavailable", description: preview.message ?? "Unable to preview files.", alertOnly: true })
      return
    }
    if (!await confirmAction({ title: "Remove this model connection?", description: describeDeletion(preview), confirmLabel: "Remove Connection", destructive: true })) return
    const result = await bridge.removeModel(modelId, preview.token)
    if (!result.ok || result.retained?.length) await confirmAction({ title: result.ok ? "Connection removed; files kept" : "Removal incomplete", description: describeDeletionResult(result), alertOnly: true })
    await refresh()
  }

  async function setInstructions(modelId: string, customInstructions: string) {
    const result = await bridge.setModelInstructions(modelId, customInstructions)
    await refresh()
    return result
  }

  async function addLocal(sourceUrl: string, displayName: string, requestPreset?: string | null) {
    const result = await bridge.addLocalModel(stageType, sourceUrl, displayName, requestPreset)
    await refresh()
    return result
  }

  async function addCloud(displayName: string, apiBaseUrl: string, apiKey: string, requestPreset: string, requestConfig?: Record<string, unknown>) {
    const result = await bridge.addCloudModel(stageType, displayName, apiBaseUrl, apiKey, requestPreset, requestConfig)
    await refresh()
    return result
  }

  async function addLocalApi(displayName: string, apiBaseUrl: string, requestPreset: string, requestConfig?: Record<string, unknown>) {
    const result = await bridge.addLocalApiModel(stageType, displayName, apiBaseUrl, requestPreset, requestConfig)
    await refresh()
    return result
  }

  return { models, activeId, progress, retry, retrying, loadError, refresh, setActive, remove, cancel, addLocal, addCloud, addLocalApi, setInstructions }
}
