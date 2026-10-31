import { Store, AlertTriangle, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { bridge } from "@/lib/api"
import { addToQueue, removeFromQueue, pauseQueue, resumeQueue, clearQueueHistory } from "@/lib/use-queue"
import { useJobs } from "@/lib/use-jobs"
import { confirmAction } from "@/lib/use-confirm"
import { describeDeletion, describeDeletionResult } from "@/lib/deletion-preview"
import type { PageId } from "@/components/shell/PrimaryNav"

interface AssetsPageProps {
  onNavigate: (page: PageId) => void
}

const JOB_LABELS = { draft: 'Ready to start', queued: 'Waiting', processing: 'Rendering',
  completed: 'Completed', failed: 'Failed', cancelled: 'Cancelled' }

export function AssetsPage({ onNavigate }: AssetsPageProps) {
  const session = useJobs()
  const queue = session.queue

  async function handleAddVideos() {
    const files = await bridge.browseVideo()
    if (files.length > 0) await addToQueue(files)
  }

  async function handleFactoryReset() {
    const preview = await bridge.previewFactoryReset()
    if (!preview.ok || !preview.token) {
      await confirmAction({ title: "Reset unavailable", description: preview.message ?? "Unable to preview files.", alertOnly: true })
      return
    }
    const ok = await confirmAction({
      title: "Delete these outputs and temporary files?",
      description: describeDeletion(preview),
      confirmLabel: "Delete Listed Files",
      destructive: true,
    })
    if (!ok) return
    const result = await bridge.factoryReset(preview.token)
    await confirmAction({ title: result.ok ? "Cleanup complete" : "Cleanup incomplete", description: result.ok ? "The listed outputs, temporary files and project caches were cleared." : describeDeletionResult(result), alertOnly: true })
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <Card className="border-border bg-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">01 // JOB QUEUE</CardTitle>
          <Button size="sm" variant="outline" onClick={handleAddVideos}>+ Add Video</Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span>{session.paused ? "Batch paused" : session.busy ? "Job active" : "Ready"}</span>
            <Button size="sm" variant="outline" disabled={!session.busy || session.paused} onClick={() => pauseQueue()}>Pause After Current</Button>
            <Button size="sm" variant="outline" disabled={session.busy || !queue.some((job) => job.status === 'queued')} onClick={() => resumeQueue()}>Resume Batch</Button>
            <Button size="sm" variant="outline" onClick={() => clearQueueHistory()}>Clear Finished History</Button>
            <span>Start new video batches from Dashboard or Nodes.</span>
          </div>
          {queue.length === 0 && <div className="text-xs text-muted-foreground">No videos queued.</div>}
          {queue.map((job) => (
            <div key={job.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
              <div className="min-w-0">
                <div className="truncate">{job.input_path.split(/[\\/]/).pop()}</div>
                <div className="text-xs text-muted-foreground">
                  {job.status === 'processing' && session.render.status === 'stopping' ? 'Stopping' : JOB_LABELS[job.status]}
                  {job.status === 'processing' ? ` · ${job.progress}% · ${session.render.status === 'stopping' ? session.render.statusText : job.status_text}` : ''}
                </div>
                {job.output_path && <div className="break-all text-xs">Output: {job.output_path}</div>}
                {job.error && <div className="break-words text-xs text-destructive">{job.error}</div>}
              </div>
              <button type="button" disabled={job.status === 'processing'} onClick={() => removeFromQueue(job.id)} title={job.status === 'processing' ? 'Stop the active job first' : 'Remove job'} className="text-muted-foreground hover:text-destructive disabled:opacity-40">
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">02 // MODELS</CardTitle>
          <Button size="sm" variant="outline" onClick={() => onNavigate("marketplace")}>
            <Store className="mr-1 h-3.5 w-3.5" /> Open Marketplace
          </Button>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Voice, STT, translation, TTS, enhancer, and filter models are now managed from the
            Marketplace - connect local downloads, cloud APIs, or local services for any pipeline stage.
          </p>
        </CardContent>
      </Card>

      <Card className="border-destructive/40 bg-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" /> 03 // FACTORY RESET
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-xs text-muted-foreground">Review and delete outputs, temporary files and project caches. Models and installed runtimes are kept.</p>
          <Button variant="destructive" onClick={handleFactoryReset}>Factory Clean</Button>
        </CardContent>
      </Card>
    </div>
  )
}
