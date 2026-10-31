import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { bridge, type CueReview, type CueReviewResult, type CueTimingResult, type RenderParams, type DialogueReadiness } from '@/lib/api'
import { runJobAction, useJobs } from '@/lib/use-jobs'
import { CueAudioPlayer } from './CueAudioPlayer'
import { confirmAction } from '@/lib/use-confirm'

export function CueReviewPanel({ inputPath, params }: { inputPath: string | null; params: Partial<RenderParams> }) {
  const jobs = useJobs()
  const [reviews, setReviews] = useState<{ id: string; name: string; created_at: number }[]>([])
  const [selected, setSelected] = useState('')
  const [review, setReview] = useState<CueReview | null>(null)
  const [index, setIndex] = useState(0)
  const [sourceText, setSourceText] = useState('')
  const [text, setText] = useState('')
  const [startSeconds, setStartSeconds] = useState('')
  const [endSeconds, setEndSeconds] = useState('')
  const [audio, setAudio] = useState<string | null>(null)
  const [timing, setTiming] = useState<(CueTimingResult & { id: string; revision: number; index: number }) | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [assistance, setAssistance] = useState<DialogueReadiness | null>(null)
  const cue = review?.cues[index]
  const dirty = !!cue && (sourceText !== cue.source_text || text !== cue.text ||
    startSeconds !== String(cue.start) || endSeconds !== String(cue.end))
  const dirtyRef = useRef(false)
  dirtyRef.current = dirty
  const busy = jobs.busy || pending
  const currentTiming = !dirty && timing?.id === review?.id && timing?.revision === review?.revision && timing?.index === index ? timing : null

  useEffect(() => {
    if (jobs.busy) return
    let live = true
    bridge.getDialogueReadiness().then(result => { if (live) setAssistance(result) })
      .catch(reason => { if (live) setAssistance({ status: 'unavailable', ready: false, message: String(reason) }) })
    return () => { live = false }
  }, [jobs.busy])


  useEffect(() => {
    if (jobs.busy) return
    let live = true
    bridge.listCueReviews().then(result => {
      if (!live) return
      if (!result.ok) { setError(result.message ?? 'Unable to load reviews'); return }
      setReviews(result.reviews)
      setSelected(current => current || result.reviews[0]?.id || '')
    }).catch(reason => { if (live) setError(String(reason)) })
    return () => { live = false }
  }, [jobs.busy])

  useEffect(() => {
    if (!selected || jobs.busy || dirtyRef.current) return
    let live = true
    bridge.getCueReview(selected).then(result => {
      if (!live || dirtyRef.current) return
      if (!result.ok || !result.review) { setError(result.message ?? 'Unable to load review'); return }
      setReview(result.review)
    }).catch(reason => { if (live) setError(String(reason)) })
    return () => { live = false }
  }, [selected, jobs.busy])

  useEffect(() => {
    setSourceText(cue?.source_text ?? '')
    setText(cue?.text ?? '')
    setStartSeconds(cue ? String(cue.start) : '')
    setEndSeconds(cue ? String(cue.end) : '')
    setAudio(null)
  }, [cue])

  function apply(result: CueReviewResult) {
    if (!result.ok || !result.review) throw new Error(result.message ?? 'The change could not be saved')
    setReview(result.review)
    return result.review
  }
  async function save() {
    if (!review) throw new Error('Select a review first')
    if (!dirty) return review
    if (!startSeconds.trim() || !endSeconds.trim() || !Number.isFinite(Number(startSeconds)) || !Number.isFinite(Number(endSeconds))) {
      throw new Error('Enter valid start and end times in seconds')
    }
    return apply(await bridge.editReviewCue(review.id, review.revision, index, sourceText, text, Number(startSeconds), Number(endSeconds)))
  }
  async function perform(work: () => Promise<unknown>) {
    setPending(true); setError(null)
    try { await work() } catch (reason) { setError(String(reason)) }
    finally { setPending(false) }
  }
  async function start(action: 'generate' | 'translate' | 'adapt' | 'supervise' | 'render') {
    const saved = await save()
    const result = await runJobAction(() => bridge.startReviewAction(saved.id, saved.revision, action, index))
    if (!result.ok) throw new Error(result.message ?? 'The job was not accepted')
  }
  const allAccepted = !!review?.cues.length && review.cues.every(item => item.accepted?.fits)
  return (
    <Card className="border-border bg-card">
      <CardHeader><CardTitle className="text-sm">Review your dub, one line at a time</CardTitle></CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-xs text-muted-foreground">Single-voice dub review. Prepare the text, correct it, then listen and accept each take. Saved reviews use their original voice and model settings. Rendering reuses accepted takes and preserves the video when one was provided.</p>
        <Button disabled={busy || !inputPath || dirty} onClick={() => void perform(async () => {
          if (!inputPath) return
          const result = await runJobAction(() => bridge.startCueReview(inputPath, params))
          if (!result.ok) throw new Error(result.message ?? 'Preparation was not accepted')
          setSelected(''); setReview(null); setIndex(0); setAudio(null)
        })}>Prepare selected media for review</Button>
        {!!reviews.length && (
          <label className="flex flex-col gap-1 text-xs">Saved review
            <select className="rounded border border-border bg-background p-2" value={selected}
              disabled={busy || dirty} onChange={event => {
                if (event.target.value === selected) return
                setReview(null); setIndex(0); setAudio(null); setError(null); setSelected(event.target.value)
              }}>
              <option value="">Choose a review</option>
              {reviews.map(item => <option key={item.id} value={item.id}>{item.name} · {new Date(item.created_at * 1000).toLocaleString()}</option>)}
            </select>
          </label>
        )}
        {review && cue && <>
          <label className="flex flex-col gap-1 text-xs">Line
            <select className="rounded border border-border bg-background p-2" value={index} disabled={busy || dirty}
              onChange={event => { setIndex(Number(event.target.value)); setError(null) }}>
              {review.cues.map((item, number) => <option key={item.cue_id || number} value={number}>
                {number + 1} · {item.start.toFixed(2)}–{item.end.toFixed(2)}s · {item.accepted ? 'Accepted' : 'Needs review'}
              </option>)}
            </select>
          </label>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs">Recognized source text
              <textarea className="min-h-24 rounded border border-border bg-background p-2" value={sourceText}
                maxLength={4000} disabled={busy} onChange={event => { setSourceText(event.target.value); setAudio(null) }} />
            </label>
            <label className="flex flex-col gap-1 text-xs">Text to speak ({review.target_lang})
              <textarea className="min-h-24 rounded border border-border bg-background p-2" value={text}
                maxLength={4000} disabled={busy} onChange={event => { setText(event.target.value); setAudio(null) }} />
            </label>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs">Line starts at (seconds)
              <input type="number" min={0} max={review.duration} step="0.01" className="rounded border border-border bg-background p-2"
                value={startSeconds} disabled={busy} onChange={event => { setStartSeconds(event.target.value); setAudio(null) }} />
            </label>
            <label className="flex flex-col gap-1 text-xs">Line ends at (seconds)
              <input type="number" min={0} max={review.duration} step="0.01" className="rounded border border-border bg-background p-2"
                value={endSeconds} disabled={busy} onChange={event => { setEndSeconds(event.target.value); setAudio(null) }} />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">Speech window: {cue.available_seconds.toFixed(2)} seconds. Editing wording clears this line's takes. Timing changes keep fitting recordings and cannot overlap lines or cut accepted speech. Listen again after moving a line. Save before switching lines.</p>
          <p className="text-xs text-muted-foreground">If a sentence is split across lines, combine it with the next phrase, then translate the complete sentence. Combining clears the two lines' takes; other accepted lines stay saved. It does not guarantee a correct translation.</p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" disabled={busy || dirty} onClick={() => void perform(async () => {
              const result = await bridge.getReviewSourceAudio(review.id, index)
              if (!result.ok || !result.audio) throw new Error(result.message ?? 'Source audio is unavailable')
              setAudio(result.audio)
            })}>Listen to original line</Button>
            <Button size="sm" disabled={busy || !dirty} onClick={() => void perform(save)}>Save changes</Button>
            <Button size="sm" variant="outline" disabled={busy || !dirty} onClick={() => {
              setSourceText(cue.source_text); setText(cue.text); setStartSeconds(String(cue.start)); setEndSeconds(String(cue.end)); setAudio(null); setError(null)
            }}>Discard unsaved changes</Button>
            <Button size="sm" variant="outline" disabled={busy || !sourceText.trim()} onClick={() => void perform(() => start('translate'))}>Translate corrected source</Button>
            <Button size="sm" variant="outline" disabled={busy || dirty || index+1 >= review.cues.length} onClick={() => void perform(async () => {
              apply(await bridge.combineReviewCues(review.id, review.revision, index))
              setAudio(null)
            })}>Combine with next phrase</Button>
            <Button size="sm" variant="outline" disabled={busy || !text.trim()} onClick={() => void perform(async () => {
              const saved = await save()
              const result = await bridge.estimateReviewTiming(saved.id, saved.revision, index)
              if (!result.ok) throw new Error(result.message ?? 'Timing could not be checked')
              setTiming({ ...result, id: saved.id, revision: saved.revision, index })
            })}>Check speech timing</Button>
            <Button size="sm" variant="outline" disabled={busy || !text.trim()} onClick={() => void perform(() => start('adapt'))}>Find wording alternatives</Button>
            <Button size="sm" variant="outline" disabled={busy || dirty || !text.trim() || !assistance?.ready} onClick={() => void perform(async () => {
              const status = await bridge.getDialogueReadiness()
              if (!status.ready || !status.writer || !status.reviewer) throw new Error(status.message)
              const confirmed = await confirmAction({
                title: 'Request shorter wording and meaning review?',
                description: `Writer: ${status.writer.label} (${status.writer.model}) at ${status.writer.endpoint}. Reviewer: ${status.reviewer.label} (${status.reviewer.model}) at ${status.reviewer.endpoint}.\n\nOriginal: ${sourceText}\nCurrent wording: ${text}\nAvailable time: ${cue.available_seconds.toFixed(2)} seconds.\n\nThe writer receives this dialogue and timing. Eligible candidates are sent to the reviewer with the original and current wording. At most two requests are made. Timing without a speech estimate remains unverified until a new take is generated. ${!status.writer.local || !status.reviewer.local ? 'Provider usage charges may apply. ' : ''}Your wording and accepted audio remain saved until you choose and save an edit.`,
                confirmLabel: 'Request suggestions',
              })
              if (confirmed) await start('supervise')
            })}>Suggest shorter wording with assistance</Button>
            <Button size="sm" disabled={busy || !text.trim()} onClick={() => void perform(() => start('generate'))}>Generate a new take</Button>
            <Button size="sm" variant="outline" disabled={busy || dirty || !cue.candidate} onClick={() => void perform(async () => {
              const result = await bridge.getReviewAudio(review.id, index)
              if (!result.ok || !result.audio) throw new Error(result.message ?? 'Audio is unavailable')
              setAudio(result.audio)
            })}>Listen to new take</Button>
            <Button size="sm" variant="outline" disabled={busy || dirty || !cue.accepted} onClick={() => void perform(async () => {
              const result = await bridge.getReviewAudio(review.id, index, true)
              if (!result.ok || !result.audio) throw new Error(result.message ?? 'Audio is unavailable')
              setAudio(result.audio)
            })}>Listen to accepted take</Button>
            <Button size="sm" disabled={busy || dirty || !cue.candidate?.fits} onClick={() => void perform(async () => {
              apply(await bridge.acceptReviewCue(review.id, review.revision, index))
            })}>Accept new take</Button>
          </div>
          {assistance && <p className="text-xs text-muted-foreground">Dialogue assistance: {assistance.message} Configure connections in Settings.</p>}
          {currentTiming && <p className={`text-xs ${currentTiming.fits === false ? 'text-amber-500' : 'text-muted-foreground'}`}>
            {currentTiming.supported && currentTiming.estimated_seconds != null && currentTiming.available_seconds != null
              ? `Estimated speech: ${currentTiming.estimated_seconds.toFixed(2)} seconds in a ${currentTiming.available_seconds.toFixed(2)}-second window. ${currentTiming.fits ? 'Likely to fit. Generate and listen before accepting.' : 'Too long. Shorten the wording and check again.'}`
              : currentTiming.message}
          </p>}
          {cue.dialogue_options && !dirty && <div className="flex flex-col gap-2 rounded border border-border p-3">
            <p className="text-xs text-muted-foreground">Check each alternative against the original meaning. A timing estimate does not confirm meaning or natural delivery. Choosing wording fills the editor; save and audition it before accepting speech.</p>
            {!cue.dialogue_options.candidates.length && <p className="text-xs">No distinct alternative was found. Edit the wording or timing and check again.</p>}
            {cue.dialogue_options.candidates.map(option => <div key={option.text} className="text-xs flex flex-col gap-1">
              <p>{option.text}</p>
              <p>{option.predicted_seconds.toFixed(2)} seconds · {option.fits ? 'Predicted to fit' : 'Still too long'}</p>
              {option.warnings.map(warning => <p key={warning} className="text-amber-500">{warning}</p>)}
              <Button size="sm" variant="outline" disabled={busy || !option.fits} onClick={() => { setText(option.text); setAudio(null) }}>Use this wording</Button>
            </div>)}
          </div>}
          {cue.dialogue_supervision && !dirty && <div className="flex flex-col gap-2 rounded border border-border p-3">
            <p className="text-xs text-muted-foreground">Assisted wording review · {cue.dialogue_supervision.writer_requests} writer request, {cue.dialogue_supervision.reviewer_requests} meaning-review request. Model opinions are advisory. Check the original meaning, then save and audition any wording you choose.</p>
            {cue.dialogue_supervision.meaning_review_protocol !== 'quoted-spans.v1' && cue.dialogue_supervision.reviewer_requests > 0 && <p className="text-xs text-amber-500">This older review has no checked source quotes. Compare its claims with the original before choosing wording.</p>}
            {cue.dialogue_supervision.outcome === 'original_fits_prediction'
              ? <p className="text-xs">The original wording already fits its prediction. No model requests were made.</p>
              : cue.dialogue_supervision.outcome === 'no_reviewed_fitting_alternative' && <p className="text-xs">No fitting alternative passed the advisory meaning check. Keep or manually edit the wording or timing.</p>}
            {cue.dialogue_supervision.outcome === 'no_reviewed_alternative' && <p className="text-xs">No alternative passed the advisory meaning check. Keep or manually edit the wording; timing still needs a generated take.</p>}
            {cue.dialogue_supervision.candidates.map(option => <div key={option.id} className="text-xs flex flex-col gap-1">
              <p>{option.text}</p>
              <p>{option.predicted_seconds == null ? 'Timing unverified — save and generate a take to measure' : `${option.predicted_seconds.toFixed(2)} seconds · ${option.fits ? 'Predicted to fit' : 'Still too long'}`} · Meaning: {option.meaning_status.replace('_', ' ')}</p>
              {[...option.warnings, ...option.meaning_reasons].map((reason, number) => <p key={number} className="text-muted-foreground">{reason}</p>)}
              {option.meaning_evidence?.map((evidence, number) => <div key={`evidence-${number}`} className="rounded border border-border p-2">
                <p>Source: {evidence.source_quote || '(no counterpart cited)'}</p>
                <p>Suggested wording: {evidence.candidate_quote || '(no counterpart cited)'}</p>
                <p className="text-muted-foreground">Model claim: {evidence.relation}. Quotes checked against supplied text; meaning still needs review.</p>
              </div>)}
              <Button size="sm" variant="outline" disabled={busy || option.fits === false || option.warnings.length > 0 || option.meaning_status !== 'preserved'} onClick={() => { setText(option.text); setAudio(null) }}>Use this wording</Button>
            </div>)}
          </div>}
          {cue.candidate && <p className={`text-xs ${cue.candidate.fits ? 'text-muted-foreground' : 'text-amber-500'}`}>
            New take: {cue.candidate.seconds.toFixed(2)} seconds. {cue.candidate.fits ? 'Fits the window. Listen before accepting.' : 'Too long. Shorten the wording and regenerate; words will not be cut.'}
          </p>}
          {cue.accepted && <p className="text-xs text-primary">Accepted take saved ({cue.accepted.seconds.toFixed(2)} seconds).</p>}
          {audio && <CueAudioPlayer key={`${review.id}-${index}-${audio.length}`} audio={audio} />}
          <Button disabled={busy || dirty || !allAccepted} onClick={() => void perform(() => start('render'))}>Render {review.output_kind === 'video' ? 'video' : 'audio'} from accepted takes</Button>
          {!allAccepted && <p className="text-xs text-muted-foreground">Accept a fitting take for every line before rendering.</p>}
        </>}
        {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  )
}
