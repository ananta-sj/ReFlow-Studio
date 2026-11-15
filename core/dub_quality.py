"""A completed export must contain the requested spoken dub, not source fallbacks."""
MUSIC_REASONS = frozenset({'likely_opening_song','marked_singing','caption_marked_song',
    'caption_music_without_dialogue','caption_marked_sound'})


class DubReviewRequired(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__(f"Dialogue review required: {report['ready']} of {report['total']} dialogue lines "
            f"are ready ({report['stage']}). The batch is paused; an incomplete dub was not published.")


def assess_readback(transcript, report, preserved=None, manifest=None):
    """A missing verification result is unavailable, never an implicit pass."""
    rows = {row['index']:row for row in report.get('cues',[])}
    unavailable = dict(preserved or {})
    for index,cue in enumerate(transcript):
        if index in unavailable:
            continue
        row = rows.get(index)
        if not row:
            unavailable[index] = 'speech_readback_unavailable'
        elif row.get('status') != 'passed_readback':
            unavailable[index] = row.get('reason') or 'speech_readback_mismatch'
    return assess(transcript,unavailable,'speech intelligibility',manifest)


def assess(transcript, unavailable, stage, manifest=None, *, allowed_fraction=0.):
    rows, total, missing = [], 0, 0
    for index,cue in enumerate(transcript):
        count = len(cue.get('source_fragments') or [cue])
        reason = unavailable.get(index)
        if reason in MUSIC_REASONS:
            continue
        total += count
        if reason:
            missing += count
            rows.append(dict(index=index,cue_id=cue.get('cue_id'),start=cue['start'],end=cue['end'],reason=reason))
    report = dict(status='needs_review' if missing else 'ready',stage=stage,total=total,
                  ready=total-missing,unresolved=missing,cues=rows,original_speech_substituted=False)
    if manifest:
        manifest.report('dub-coverage',report)
    if total and missing/total > allowed_fraction:
        raise DubReviewRequired(report)
    return report
