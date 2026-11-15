"""Same-language embedded captions: spoken text plus explicit non-speech evidence."""
import html
import json
import re
import subprocess
import unicodedata
from pathlib import Path

LANGUAGES = {'ja': {'ja', 'jpn'}, 'en': {'en', 'eng'}, 'hi': {'hi', 'hin'},
             'fr': {'fr', 'fra', 'fre'}, 'de': {'de', 'deu', 'ger'}, 'es': {'es', 'spa'},
             'ko': {'ko', 'kor'}, 'zh': {'zh', 'zho', 'chi'}, 'ru': {'ru', 'rus'},
             'pt': {'pt', 'por'}, 'it': {'it', 'ita'}, 'ar': {'ar', 'ara'}}


def generic_speaker(label):
    # These SDH role labels can denote different people in successive cues.
    return unicodedata.normalize('NFKC',label).casefold() in {
        '子供','子ども','男','女','男性','女性','客','村人','店員','兵士','老人','少年','少女',
        'child','boy','girl','man','woman','guest','customer','villager','soldier','guard','worker',
    }


def classify(segments, sdh=False):
    dialogue, events, markers = [], [], []
    sound = re.compile(r'(?:の.*(?:音|声|息)|くしゃみ|鳴き声|うなり声|ほえ声|笑い声|ため息|泣き声|せき|咳|拍手|足音|music|singing|sighs?|gasps?|laughs?|barks?)', re.I)
    known_labels = set()
    if sdh:
        for item in segments:
            normalized=unicodedata.normalize('NFKC',html.unescape(re.sub(r'<[^>]+>','',item['text']))).strip()
            prefix=re.match(r'^\(([^()\n]{1,80})\)\s*',normalized)
            if prefix and not sound.search(prefix.group(1)):
                known_labels.add(prefix.group(1).strip())
    for original in segments:
        cue = dict(original)
        text = unicodedata.normalize('NFKC', html.unescape(re.sub(r'<[^>]+>', '', cue['text']))).strip()
        if any(symbol in text for symbol in ('♪', '♬')):
            bare = re.sub(r'[♪♬~〜～\s]+', '', text)
            if not bare:
                markers.append(dict(start=cue['start'], end=cue['end'], close=text.startswith(('~', '〜', '～'))))
            else:
                events.append(dict(start=cue['start'], end=cue['end'], reason='caption_marked_song'))
            continue
        label = None
        if sdh:
            prefix = re.match(r'^\(([^()\n]{1,80})\)\s*', text)
            if prefix:
                label = prefix.group(1).strip()
                text = text[prefix.end():].strip()
                if sound.search(label):
                    if not text:
                        events.append(dict(start=cue['start'], end=cue['end'], reason='caption_marked_sound'))
                        continue
                    label = None
                elif not text:
                    events.append(dict(start=cue['start'], end=cue['end'], reason='caption_annotation'))
                    continue
            # Inline kana readings annotate the kanji rather than spoken words.
            text = re.sub(r'(?<=[\u3400-\u9fff])\([ぁ-ゖァ-ヺー]+\)', '', text)
            # A caption can contain a handoff as well as its opening label.
            # Such audio must not become a single-character voice anchor.
            inline_labels={value.strip() for value in re.findall(r'\(([^()\n]{1,80})\)',text)} & known_labels
            if inline_labels - ({label} if label else set()):
                cue['multiple_caption_speakers']=True
        text = ' '.join(text.split())
        if not text:
            continue
        cue.update(text=text, source_text=text, source_caption=True)
        if label:
            cue['speaker_hint'] = label
            cue['speaker_generic'] = generic_speaker(label)
            cue['speaker_collective'] = label.endswith('たち') or label in {'一同','全員'} or label.casefold() in {'all','crowd','children','everyone','group'}
        dialogue.append(cue)
    opened = None
    for marker in markers:
        if not marker['close']:
            opened = marker['start']
            continue
        start = opened if opened is not None else 0.
        end = marker['end']
        # A music bed under actual dialogue must not restore Japanese speech.
        if not any(cue['start'] < end and cue['end'] > start for cue in dialogue):
            events.append(dict(start=start, end=end, reason='caption_music_without_dialogue'))
        opened = None
    if opened is not None:
        end = max((cue['end'] for cue in segments), default=opened)
        if end > opened and not any(cue['start'] < end and cue['end'] > opened for cue in dialogue):
            events.append(dict(start=opened, end=end, reason='caption_music_without_dialogue'))
    # Preserve only portions that cannot reintroduce speech over the new dub.
    from core.diarization import clear_ranges
    safe_events = []
    for event in events:
        for start, end in clear_ranges(event['start'], event['end'], [(c['start'], c['end']) for c in dialogue]):
            if end > start:
                safe_events.append(dict(start=start, end=end, reason=event['reason']))
    return dialogue, safe_events


def extract(video_path, language, folder):
    from core.render_context import run_process
    from core.srt_utils import parse_srt
    allowed = LANGUAGES.get(language, {language})
    if language == 'auto':
        return None
    probe = run_process(['ffprobe', '-v', 'error', '-select_streams', 's', '-show_streams', '-of', 'json', str(video_path)],
                        check=True, capture_output=True, text=True, timeout=60)
    streams = json.loads(probe.stdout).get('streams', [])
    suitable = [stream for stream in streams if stream.get('codec_name') in ('subrip', 'ass', 'ssa', 'mov_text', 'webvtt')
                and stream.get('tags', {}).get('language', '').lower() in allowed]
    if not suitable:
        return None
    suitable.sort(key=lambda stream: ('sdh' not in stream.get('tags', {}).get('title', '').lower(), stream['index']))
    stream = suitable[0]
    path = Path(folder)/'embedded-source.srt'
    run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(video_path), '-map', '0:'+str(stream['index']),
                 '-c:s', 'srt', str(path)], check=True, capture_output=True, timeout=120)
    segments = parse_srt(str(path))
    sdh = ('sdh' in stream.get('tags', {}).get('title', '').lower()
           or bool(stream.get('disposition', {}).get('hearing_impaired')))
    dialogue, events = classify(segments, sdh)
    if not dialogue:
        return None
    if language == 'ja' and not any(re.search(r'[\u3040-\u30ff\u3400-\u9fff]', cue['text']) for cue in dialogue):
        return None  # A language tag alone is not evidence of Japanese text.
    return dict(language=language, stream_index=stream['index'], sdh=sdh,
                dialogue=dialogue, preserved_events=events)
