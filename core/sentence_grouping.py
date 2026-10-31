"""Bounded complete-sentence grouping for single-voice stronger recognition."""
import re


def group_sentences(transcript, max_seconds=30, max_gap=.6, max_characters=1500):
    grouped, pending = [], None
    def terminal(text):
        return bool(re.search(r'[.!?।॥][\"\u201d\u2019]*$',text.strip()))
    for original in transcript:
        cue = dict(original)
        cue['source_fragments'] = [dict(original)]
        if (pending is None and grouped and cue.get('asr_block_boundary')
                and transcript.language == 'en' and re.match(r'^[a-z]',cue['text'])
                and re.search(r'\b(?:and|or|but|because|not)\.$',grouped[-1]['text'])):
            previous = grouped[-1]
            if (0 <= cue['start']-previous['end'] <= max_gap
                    and cue['end']-previous['start'] <= max_seconds
                    and len(previous['text'])+len(cue['text'])+1 <= max_characters
                    and all(previous.get(key) == cue.get(key) for key in ('speaker','speaker_id'))):
                pending = grouped.pop()
                pending['text'] = pending['text'][:-1]
                pending['boundary_punctuation_join'] = True
        if pending is not None:
            can_join = (0 <= cue['start']-pending['end'] <= max_gap
                        and cue['end']-pending['start'] <= max_seconds
                        and len(pending['text'])+len(cue['text'])+1 <= max_characters
                        and all(pending.get(key) == cue.get(key) for key in ('speaker','speaker_id')))
            if can_join:
                pending['end'] = cue['end']
                pending['text'] = pending['text'].strip()+' '+cue['text'].strip()
                pending['source_fragments'].extend(cue['source_fragments'])
            else:
                grouped.append(pending)
                pending = cue
        else:
            pending = cue
        if terminal(pending['text']):
            grouped.append(pending)
            pending = None
    if pending is not None:
        pending['incomplete_sentence_tail'] = True
        grouped.append(pending)
    return transcript.with_segments(grouped)
