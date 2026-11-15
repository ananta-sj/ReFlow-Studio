import { useEffect, useState } from 'react'
import { bridge, type BatchReviewResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { runJobAction, useJobs } from '@/lib/use-jobs'
import { CueAudioPlayer } from './CueAudioPlayer'

const labels: Record<string, string> = {
  character_uncertain: 'Confirm the character voice',
  no_clean_character_reference: 'Check the source voice reference',
  mixed_source_voices: 'More than one voice may be present',
  merged_character_group: 'Confirm which character is speaking',
  short_unlabelled_reply: 'Confirm the voice for this short reply',
  no_detected_source_voice: 'Check this quiet or unclear line',
  source_transcription_uncertain: 'Check the source dialogue',
  dialogue_onset: 'Check when the line starts',
  delivery_duration: 'Check delivery speed and pauses',
  voice_pitch: 'Check the character’s pitch',
  speech_readback_mismatch: 'Check the spoken words',
  speech_readback_unavailable: 'A listening check is needed',
  no_measurable_speech: 'Check whether the line is audible',
  voice_identity_uncertain: 'Confirm this character voice',
  multiple_source_speakers: 'Several characters speak together',
  character_reference_uncertain: 'A clear character sample is needed',
  timing_overflow: 'The translated line does not fit its speech window',
}
function reasonLabel(reason: string): string {
  if (reason.startsWith('original_audio_retained:')) return 'Original audio was retained for this line'
  return labels[reason] ?? reason.replaceAll('_', ' ')
}
function timeLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'Time unavailable'
  const seconds = Math.max(0, Math.floor(value))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function BatchReviewSummary({ outputPath, failed=false }: { outputPath: string | null; failed?:boolean }) {
  const [data, setData] = useState<BatchReviewResponse | null>(null)
  const jobs=useJobs()
  const [recovering,setRecovering]=useState(false)
  const [error,setError]=useState('')
  const [audio,setAudio]=useState<{cueId:string;data:string}|null>(null)
  const [loadingTake,setLoadingTake]=useState(false)
  useEffect(() => {
    let active = true
    setData(null)
    setAudio(null);setError('')
    const request = failed ? bridge.getFailedRenderReview() : outputPath ? bridge.getRenderReview(outputPath) : null
    if (request) void request.then(
      value => { if (active) setData(value) },
      () => { if (active) setData(null) },
    )
    return () => { active = false }
  }, [outputPath, failed])
  const review = data?.ok ? data.review : null
  if (!review || review.status !== 'needs_review') return null
  return <section className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3" aria-label="Dialogue review">
    <h3 className="text-sm font-semibold">Dialogue review: {review.cues.length} lines to check</h3>
    {review.coverage && <p className="mt-1 text-xs">{review.coverage.ready} of {review.coverage.total} dialogue lines ready. {review.coverage.unresolved} need a decision.</p>}
    <p className="mt-1 text-xs text-muted-foreground">{failed ? 'This episode was not exported. Confirm the flagged voices or wording before retrying.' : 'Listen to these moments before accepting the dub. Automatic checks cannot confirm natural acting.'}</p>
    {failed && <div className="mt-2">
      <Button size="sm" disabled={jobs.busy || recovering} onClick={() => {
        setRecovering(true);setError('')
        void runJobAction(() => bridge.recoverFailedReview()).then(result => {
          if (!result.ok) setError(result.message ?? 'Recovery could not start')
        }).catch(reason => setError(String(reason))).finally(() => setRecovering(false))
      }}>Recover into editable review</Button>
      <p className="mt-1 text-xs text-muted-foreground">Reuses saved dialogue and translations without transcribing again. Audio preparation runs again. Previous speech takes are not imported or accepted. Open the new saved review below when preparation finishes.</p>
      {error && <p role="alert" className="mt-1 text-xs text-destructive">{error}</p>}
    </div>}
    <div className="mt-3 max-h-80 space-y-2 overflow-y-auto">
      {review.cues.map((cue, ordinal) => <details key={cue.cue_id ?? ordinal} className="rounded border border-border p-2 text-xs">
        <summary className="cursor-pointer font-medium">{timeLabel(cue.start)} — {cue.reasons.map(reasonLabel).join('; ')}</summary>
        {cue.text && <p className="mt-2 whitespace-pre-wrap">{cue.text}</p>}
        {cue.observed && <p className="mt-1 text-muted-foreground">Readback heard: {cue.observed}</p>}
        {cue.source_text && <p className="mt-1 text-muted-foreground">Source: {cue.source_text}</p>}
        {cue.timing && <p className="mt-1 text-muted-foreground">
          Saved take: {cue.timing.measured_seconds.toFixed(2)} seconds · Window: {cue.timing.available_seconds.toFixed(2)} seconds · Over by {cue.timing.excess_seconds.toFixed(2)} seconds.
        </p>}
        {failed && cue.has_saved_take && cue.cue_id && <Button className="mt-2" size="sm" variant="outline"
          disabled={jobs.busy || loadingTake} onClick={() => {
            setLoadingTake(true);setError('')
            void bridge.getFailedRenderTake(cue.cue_id!).then(result => {
              if (result.ok && result.audio) setAudio({cueId:cue.cue_id!,data:result.audio})
              else setError(result.message ?? 'Saved take is unavailable')
            }).catch(reason => setError(String(reason))).finally(() => setLoadingTake(false))
          }}>Load saved overlong take</Button>}
        {audio && audio.cueId===cue.cue_id && <CueAudioPlayer audio={audio.data} />}
      </details>)}
    </div>
  </section>
}
