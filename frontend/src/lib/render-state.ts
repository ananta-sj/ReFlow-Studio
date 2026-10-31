import type { SourceLanguageFeedback } from "./api"

export type RenderStatus = "idle" | "running" | "stopping" | "finished" | "error"

export interface RenderState {
  status: RenderStatus
  percent: number
  statusText: string
  activeStageId: string | null
  outputPath: string | null
  errorMessage: string | null
  sourceFeedback: SourceLanguageFeedback | null
  inputPath: string | null
}

export const INITIAL: RenderState = {
  status: "idle",
  percent: 0,
  statusText: "",
  activeStageId: null,
  outputPath: null,
  errorMessage: null,
  sourceFeedback: null,
  inputPath: null,
}

export function applyRenderEvent(prev: RenderState, event: string, payload: unknown): RenderState {
  const data = payload as Record<string, unknown>
  switch (event) {
    case "render_started": return { ...INITIAL, status: "running", statusText: "Starting…", inputPath: data.inputPath as string }
    case "render_stopping": return { ...prev, status: "stopping", statusText: "Stopping… waiting for active work to exit." }
    case "render_stopped": return INITIAL
    case "progress": return prev.status === "stopping" ? prev : { ...prev, status: "running", percent: data.percent as number, statusText: data.status as string }
    case "stage": return prev.status === "stopping" ? prev : { ...prev, activeStageId: data.stageId as string }
    case "source_language": return prev.status === "stopping" ? prev : { ...prev, sourceFeedback: payload as SourceLanguageFeedback }
    case "render_finished": return { ...prev, status: "finished", percent: 100, activeStageId: null, outputPath: data.outputPath as string }
    case "render_error": return { ...prev, status: "error", activeStageId: null, errorMessage: data.message as string }
    default: return prev
  }
}

export function isRenderBusy(state: RenderState): boolean {
  return state.status === "running" || state.status === "stopping"
}
