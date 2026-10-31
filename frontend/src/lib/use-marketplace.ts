import { confirmAction } from "./use-confirm"
import { describeDeletion, describeDeletionResult } from './deletion-preview'
import { useCallback, useEffect, useState } from "react"
import { subscribe } from "@/lib/events"
import { bridge, type ModelDownloadProgress, type ModelEntry, type StageType } from "@/lib/api"

export function useMarketplace(stageType: StageType) {
  const [models, setModels] = useState<ModelEntry[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [progress, setProgress] = useState<Record<string, ModelDownloadProgress>>({})

  const refresh = useCallback(async () => {
    const [list, activeMap] = await Promise.all([bridge.listModels(stageType), bridge.getActiveModels()])
    setModels(list)
    setActiveId(activeMap[stageType]?.id ?? null)
  }, [stageType])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const unsubs = [
      subscribe("model_download_progress", (payload) => {
        const p = payload as ModelDownloadProgress
        setProgress((prev) => ({ ...prev, [p.modelId]: p }))
      }),
      subscribe("model_installed", () => {
        refresh()
      }),
      subscribe("model_download_stopping", () => { refresh() }),
      subscribe("model_download_finished", (payload) => {
        const { modelId } = payload as { modelId: string }
        setProgress((prev) => { const next = { ...prev }; delete next[modelId]; return next })
        refresh()
      }),
      subscribe("model_download_error", (payload) => {
        const { modelId } = payload as { modelId: string; message: string }
        setProgress((prev) => {
          const next = { ...prev }
          delete next[modelId]
          return next
        })
        refresh()
      }),
    ]
    return () => unsubs.forEach((fn) => fn())
  }, [refresh])

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

  return { models, activeId, progress, refresh, setActive, remove, cancel, addLocal, addCloud, addLocalApi, setInstructions }
}
