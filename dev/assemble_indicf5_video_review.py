"""Diagnostic moving-video render from approved text and completed native speech."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def stamp(seconds):
    milliseconds = round(seconds * 1000)
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, ms = divmod(rest, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}'


def main():
    import numpy as np
    import soundfile as sf
    from core.render_context import RenderContext, bind_job, run_process
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    receipt = args.receipt.resolve()
    if ROOT / 'docs/validation' not in receipt.parents:
        raise ValueError('Receipt outside validation root')
    generation = json.loads(receipt.read_text(encoding='utf-8'))
    draft_path = Path(generation['video_draft']).resolve()
    directory = Path(generation['directory']).resolve()
    if any(ROOT / 'docs/validation' not in path.parents for path in (draft_path, directory)):
        raise ValueError('Draft or speech outside validation root')
    if not generation['completed'] or digest(draft_path) != generation['video_draft_sha256']:
        raise ValueError('Speech incomplete or approved text changed')
    if not generation['video_translation_approval']['human_translation_accepted']:
        raise ValueError('Text not approved')
    if generation['video_translation_approval'].get('draft_sha256') != digest(draft_path):
        raise ValueError('Draft differs from pinned human approval')
    draft = json.loads(draft_path.read_text(encoding='utf-8'))
    source_receipt_path = ROOT / 'docs/validation' / draft['source_receipt']
    source_receipt = json.loads(source_receipt_path.read_text(encoding='utf-8'))
    source = Path(source_receipt['source']).resolve()
    if source != (ROOT / 'Sample/2.mp4').resolve() or digest(source) != source_receipt['source_sha256']:
        raise ValueError('Original moving-video source changed')
    seconds = draft['source_excerpt_seconds']
    if seconds != source_receipt['selected_video_end_seconds']:
        raise ValueError('Fixture endpoint mismatch')
    rows = generation['cases']
    destination = ROOT / 'docs/validation' / ('2026-10-06-indicf5-video-review-'+uuid.uuid4().hex[:8])
    report = dict(completed=False, automatic_media_pass=False, human_quality_accepted=False,
        production_voice_route_changed=False, shared_process_helper_fixed=True,
        diagnostic_bridge=True, production_route_tested=False,
        background_preservation_tested=False, original_audio_mixed=False,
        source_receipt=str(source_receipt_path), source_sha256=source_receipt['source_sha256'],
        generation_receipt=str(receipt), generation_receipt_sha256=digest(receipt),
        draft_sha256=digest(draft_path), directory=str(destination), cues=[],
        sentence_pause_seconds=0.2, post_generation_tempo_changed=False)
    job = RenderContext(ROOT / 'temp')
    try:
        with bind_job(job):
            work = job.workspace / 'video-review'
            work.mkdir()
            track = np.zeros(round(seconds*24000), dtype='int16')
            subtitle_rows, used = [], set()
            previous_end = 0
            for index, cue in enumerate(draft['cues']):
                if not previous_end <= cue['start'] < cue['end'] <= seconds:
                    raise ValueError('Cue windows overlap or exceed source timeline')
                previous_end = cue['end']
                selected = [row for row in rows if row['cue_index'] == index]
                selected.sort(key=lambda row: row['sentence_index'])
                if not selected or [row['sentence_index'] for row in selected] != list(range(len(selected))):
                    raise ValueError('Sentence order incomplete')
                if ' '.join(row['text'] for row in selected) != cue['text']:
                    raise ValueError('Generated text differs from approved cue')
                parts = []
                for i, row in enumerate(selected):
                    if row['name'] in used or row['cue_start'] != cue['start'] or row['cue_end'] != cue['end']:
                        raise ValueError('Duplicate sentence or cue timing mismatch')
                    used.add(row['name'])
                    audio = directory / row['name'] / 'listening.wav'
                    if digest(audio) != row['listening_sha256']:
                        raise ValueError('Generated speech changed')
                    samples, rate = sf.read(audio, dtype='int16')
                    if rate != 24000 or samples.ndim != 1 or len(samples) != row['expected_target_frames']:
                        raise ValueError('Invalid generated speech format/duration')
                    if i:
                        parts.append(np.zeros(4800, dtype='int16'))
                    parts.append(samples)
                joined = np.concatenate(parts)
                start = round(cue['start']*24000)
                end = round(cue['end']*24000)
                if len(joined) > end-start:
                    raise ValueError(f'Cue {index+1} needs {len(joined)/24000:.3f}s; available {(end-start)/24000:.3f}s. No words cut or tempo forced.')
                track[start:start+len(joined)] = joined
                report['cues'].append(dict(index=index, start=cue['start'], end=cue['end'],
                    speech_seconds=len(joined)/24000, spare_seconds=(end-start-len(joined))/24000,
                    sentence_files=[row['name'] for row in selected]))
                subtitle_rows.append(f'{index+1}\n{stamp(cue["start"])} --> {stamp(cue["end"])}\n{cue["text"]}\n')
            if len(used) != len(rows):
                raise ValueError('Unused generated speech')
            voice = work / 'hindi-voice.wav'
            sf.write(voice, track, 24000, subtype='PCM_16')
            restored, rate = sf.read(voice, dtype='int16')
            if rate != 24000 or not np.array_equal(restored, track):
                raise ValueError('Timeline assembly altered samples')
            subtitles = work / 'hindi-subtitles.srt'
            subtitles.write_text('\n'.join(subtitle_rows), encoding='utf-8')
            output = work / 'abhishek-hindi-review.mp4'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(source),
                '-i', str(voice), '-i', str(subtitles), '-map', '0:v:0', '-map', '1:a:0', '-map', '2:0',
                '-t', str(seconds), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                '-pix_fmt', 'yuv420p', '-threads', '2', '-c:a', 'aac', '-b:a', '192k',
                '-c:s', 'mov_text', '-metadata:s:a:0', 'language=hin', '-metadata:s:s:0', 'language=hin',
                '-movflags', '+faststart', str(output)], check=True, timeout=300)
            result = run_process(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output)],
                                 check=True, capture_output=True, text=True, timeout=60)
            info = json.loads(result.stdout)
            if {s['codec_type'] for s in info['streams']} != {'video', 'audio', 'subtitle'}:
                raise ValueError('Expected exactly video, Hindi audio and subtitle stream types')
            if abs(float(info['format']['duration'])-seconds) > 0.1:
                raise ValueError('Rendered timeline duration changed')
            extracted_subtitles = work / 'verified-subtitles.srt'
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(output), '-map', '0:s:0',
                         '-c:s', 'srt', str(extracted_subtitles)], check=True, timeout=60)
            extracted_text = extracted_subtitles.read_text(encoding='utf-8-sig').strip()
            blocks = extracted_text.replace('\r\n', '\n').split('\n\n')
            if [' '.join(block.splitlines()[2:]) for block in blocks] != [cue['text'] for cue in draft['cues']]:
                raise ValueError('Muxed subtitles do not preserve approved Hindi text')
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(output), '-map', '0:v:0',
                '-map', '0:a:0', '-f', 'null', os.devnull], check=True, timeout=180)
            run_process(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(voice), '-f', 'null', os.devnull],
                        check=True, timeout=60)
            if digest(source) != source_receipt['source_sha256']:
                raise ValueError('Original source changed during rendering')
            report.update(completed=True, automatic_media_pass=True, full_decode_pass=True,
                          sample_exact_voice_timeline=True, source_unchanged=True,
                          subtitle_text_roundtrip_pass=True,
                          seconds=seconds, streams=info['streams'], video_sha256=digest(output),
                          voice_sha256=digest(voice), subtitle_sha256=digest(subtitles))
            (work / 'review-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            job.publish(work, destination)
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        job.cleanup()
        report['workspace_removed'] = not job.workspace.exists()
        destination.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'completed':report['completed'], 'directory':str(destination), 'error':report.get('error')}, ensure_ascii=True))


if __name__ == '__main__':
    main()
