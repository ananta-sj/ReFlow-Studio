import { useEffect, useId, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { CueReview, ReviewCue } from '@/lib/api'

const reasons = {
  too_long: 'Take is too long', ends_early: 'Check the short ending',
  delivery_uncertain: 'Check delivery', words_uncertain: 'Check spoken words',
  generation_failed: 'Generation failed', timing_and_words: 'Listen to acting and meaning',
}

export function CueTranscript({ review, selectedIndex, disabled, showAccepted, onlyUnassigned, onSelect }: {
  review: CueReview; selectedIndex: number; disabled: boolean; showAccepted: boolean
  onlyUnassigned: boolean; onSelect: (index: number) => void
}) {
  const [query, setQuery] = useState('')
  const headingId = useId()
  const selectedButton = useRef<HTMLButtonElement>(null)
  const lastSelection = useRef(`${review.id}-${selectedIndex}`)
  useEffect(() => {
    const selection = `${review.id}-${selectedIndex}`
    if (lastSelection.current !== selection) {
      selectedButton.current?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    }
    lastSelection.current = selection
  }, [review.id, selectedIndex])
  const hasReference = (cue: ReviewCue) => !!cue.speaker && !!review.speaker_references?.includes(cue.speaker)
  const remaining = review.cues.filter(cue => !cue.accepted).length
  const unassigned = review.cues.filter(cue => !hasReference(cue)).length
  const search = query.trim().normalize('NFKC').toLocaleLowerCase()
  const matching = review.cues.flatMap((cue, index) => {
    const matches = [cue.source_text, cue.text, cue.speaker ?? ''].some(value =>
      value.normalize('NFKC').toLocaleLowerCase().includes(search))
    return matches && (showAccepted || !remaining || !cue.accepted) &&
      (!onlyUnassigned || !unassigned || !hasReference(cue)) ? [index] : []
  })
  const visible = new Set([...matching, selectedIndex])
  const unresolved = matching.filter(index => !review.cues[index].accepted)
  const next = unresolved.find(index => index > selectedIndex) ?? unresolved[0]

  function status(cue: ReviewCue) {
    if (review.speaker_matching && (review.speaker_dirty || !hasReference(cue))) return 'Needs character reference'
    if (cue.translation_pending) return 'Needs translation'
    if (cue.accepted) return 'Accepted take saved'
    if (cue.first_pass) return reasons[cue.first_pass.reason]
    if (cue.candidate) return cue.candidate.fits ? 'Candidate ready to audition' : 'Take is too long'
    return 'Needs a take'
  }

  return <section aria-labelledby={headingId} className="min-w-0 rounded-md border border-border">
    <div className="flex flex-col gap-3 border-b border-border p-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 flex-1">
        <h3 id={headingId} className="text-sm font-medium">Dialogue</h3>
        <label className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">Search dialogue or character
          <input type="search" value={query} onChange={event => setQuery(event.target.value)}
            className="w-full rounded border border-border bg-background p-2 text-foreground focus-visible:outline-2 focus-visible:outline-ring" />
        </label>
      </div>
      <Button size="sm" variant="outline" disabled={disabled || next === undefined || next === selectedIndex}
        onClick={() => { if (!disabled && next !== undefined) onSelect(next) }}>Next unresolved line</Button>
    </div>
    <div className="max-h-72 overflow-auto">
      <table className="w-full min-w-xl text-left text-xs" aria-labelledby={headingId}>
        <thead className="sticky top-0 bg-card text-muted-foreground"><tr>
          <th scope="col" className="p-3 font-medium">Line / time</th>
          <th scope="col" className="p-3 font-medium">Character</th>
          <th scope="col" className="p-3 font-medium">Source / translation</th>
          <th scope="col" className="p-3 font-medium">Review</th>
        </tr></thead>
        <tbody>{review.cues.map((cue, index) => visible.has(index) && <tr key={cue.cue_id ?? index}
          className={index === selectedIndex ? 'border-t border-border bg-primary/10' : 'border-t border-border'}>
          <td className="p-3 align-top"><button type="button" data-cue-index={index}
            ref={index === selectedIndex ? selectedButton : undefined}
            aria-label={`Select line ${index + 1}`} aria-current={index === selectedIndex ? 'true' : undefined}
            disabled={disabled} onClick={() => { if (!disabled) onSelect(index) }}
            className="rounded text-left text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50">
            Line {index + 1}<span className="block whitespace-nowrap text-muted-foreground">{cue.start.toFixed(2)}–{cue.end.toFixed(2)}s</span>
          </button></td>
          <td className="p-3 align-top">{cue.speaker || (review.speaker_matching ? 'Unassigned' : 'Selected voice')}</td>
          <td className="max-w-md p-3 align-top break-words"><p className="text-muted-foreground">{cue.source_text}</p><p className="mt-1">{cue.text}</p></td>
          <td className="p-3 align-top">{status(cue)}{cue.accepted && status(cue) !== 'Accepted take saved' &&
            <span className="mt-1 block text-muted-foreground">Accepted take saved</span>}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className="border-t border-border p-3 text-xs text-muted-foreground" role="status">
      {matching.length ? `${matching.length} matching lines. ` : 'No lines match the current filters. '}
      The selected line stays visible. {disabled ? 'Save or discard edits and wait for active work before changing lines.' : 'Select a line to inspect it below.'}
    </p>
  </section>
}
