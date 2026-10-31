"""Editorial budget review against retained live ASR/MT; never an automatic MT fix."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'core')]
os.environ.update(REFLOW_OFFLINE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
os.environ['PATH'] = str(ROOT / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true', help='Generate fresh takes after all budget checks pass')
    args = parser.parse_args()
    from core import cue_review
    from core.pipeline import ReflowPipeline
    from core.providers import resolve
    from core.render_context import RenderContext, bind_job, run_process
    from core.settings import Settings
    import soundfile as sf

    base = ROOT / 'docs/validation'
    raw_receipt = base / '2026-10-08-strong-whisper-app-review-9ad56e5a.json'
    raw = read(raw_receipt)
    original = read(raw['review_manifest'])
    draft = read(base / '2026-10-08-full-video-spoken-hindi-draft.json')
    integrated = read(base / '2026-10-09-approved-shot-full-video-55b89369.json')
    prior = read(integrated['review_manifest'])
    source = Path(raw['source'])
    assert raw['completed'] and raw['source_sha256'] == cue_review.digest(source)
    assert len(original['cues']) == 14
    folder = base / ('2026-10-09-budgeted-hindi-review-' + uuid.uuid4().hex[:8])
    folder.mkdir()
    pipe = ReflowPipeline()
    pipe.output_dir = str(folder)
    settings = Settings()
    tts = resolve.resolve_tts(pipe.registry, 'cpu')
    assert tts.engine_id == 'indicf5'
    reference = resolve.confirmed_reference(pipe.registry)
    profile_hash = cue_review.digest(tts.profile_path)
    registry_hash = cue_review.digest(ROOT / 'models.json')
    report = dict(completed=False, preflight_only=not args.render, live_asr=False, live_translation=False,
        live_tts=args.render, wording_origin='Explicit assistant editorial review, not raw engine output',
        human_new_video_accepted=False, human_new_wording_accepted=False,
        raw_preparation_receipt=str(raw_receipt), source_sha256=raw['source_sha256'],
        approved_baseline_preserved=True, new_packages=False, tempo_changed=False,
        source_word_alignment_automatic=False, background_separation_live=False,
        registry_sha256=registry_hash, profile_sha256=profile_hash, cues=[])
    rows = deepcopy(original['cues'])
    for index in range(10):
        case = draft['cases'][index]
        assert (case['start'], case['end']) == (rows[index]['start'], rows[index]['end'])
        rows[index]['text'] = case['translation']
    rows[10]['text'] = 'नहीं। फिर खाली जगह भरने को एक और फीका दृश्य। अब एक इंसानी कहानी: रसोई में चिट्ठियाँ खोलता एक साधारण आदमी बताता है कि इस मुद्दे का उस पर क्या असर पड़ा।'
    rows[11]['text'] = 'ख़बरों में कोई बताता रहता है कि क्या हो रहा है। मैं सुनता भी नहीं। बस ख़बरें हैं। बस ख़बरें।'
    # Preserve reviewed question/shot PCM and existing explicit tail anchors.
    # These anchors have not received full-video human acceptance.
    rows[12].update(text=prior['cues'][11]['text'], end=116.0)
    rows[13].update(start=116.19, text=prior['cues'][12]['text'])
    job = RenderContext(ROOT / 'temp')
    started = time.monotonic()
    try:
        with bind_job(job):
            retained = Path(integrated['review_manifest']).parent / prior['cues'][11]['accepted']['file']
            assert cue_review.digest(retained) == prior['cues'][11]['accepted']['sha256']
            for index, cue in enumerate(rows):
                cue.update(candidate=None, accepted=None)
                available = (rows[index+1]['start'] if index+1 < len(rows) else cue['end']) - cue['start']
                cue['available_seconds'] = available
                estimated = sf.info(retained).duration if index == 12 else tts.estimate_duration_seconds(cue['text'])
                record = dict(cue=index+1, start=cue['start'], end=cue['end'], available_seconds=available,
                    source=cue['source_text'], raw_translation=original['cues'][index]['text'], text=cue['text'],
                    estimated_seconds=estimated, fits=estimated <= available + .001,
                    wording_origin='Preserved reviewed shot composition' if index == 12 else
                        'Previously approved spoken wording' if index < 10 else 'Assistant editorial adaptation',
                    speech_origin='retained reviewed PCM' if index == 12 else 'new inference' if args.render else 'not generated')
                report['cues'].append(record)
                print('Cue', index+1, round(estimated,3), '/', round(available,3), 'seconds', flush=True)
            assert all(row['fits'] for row in report['cues']), 'A draft still exceeds its native budget'
            report['all_14_budget_checks_passed'] = True
            (folder / 'draft-and-budgets.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if not args.render:
                report['completed'] = True
                return
            store = cue_review.ReviewStore(folder)
            identifier = uuid.uuid4().hex
            work = store.folder(identifier)
            work.mkdir()
            shutil.copy2(source, work / 'source-video.mp4')
            shutil.copy2(reference, work / 'reference.wav')
            background = Path(integrated['review_manifest']).parent / 'background.wav'
            assert cue_review.digest(background) == prior['assets']['background.wav']
            shutil.copy2(background, work / 'background.wav')
            report['background_origin'] = 'Retained source separation from earlier validated workflow'
            for index, cue in enumerate(rows):
                wave = work / ('take-' + str(index+1) + '.wav')
                if index == 12:
                    shutil.copy2(retained, wave)
                else:
                    print('Generating cue', index+1, flush=True)
                    tts.synthesize(cue['text'], str(wave), 'hi', reference)
                info = sf.info(wave)
                measured = info.frames / info.samplerate
                record = report['cues'][index]
                assert abs(measured-record['estimated_seconds']) <= 1 / info.samplerate
                assert measured <= cue['available_seconds'] + .001
                record.update(measured_seconds=measured, file=str(wave), sha256=cue_review.digest(wave))
                if index != 12:
                    record['generation_result'] = deepcopy(tts.last_result)
                take = dict(file=wave.name, seconds=round(measured*1000)/1000,
                    fits=True, sha256=record['sha256'])
                # 'accepted' is the review store's mechanical render gate here;
                # this evaluator selection is explicitly not human approval.
                cue.update(candidate=dict(take), accepted=dict(take))
            tts.release()
            report['speech_worker_released'] = not getattr(job, '_indicf5_sessions', {})
            manifest = dict(version=1,id=identifier,revision=1,created_at=time.time(),name=source.name,
                duration=original['duration'],target_lang='hi',speech_language='hi',source_language='en',
                actor='CLONED_USER',device='cpu',configuration=cue_review.configuration(pipe,settings),
                video_asset='source-video.mp4',assets={p.name:cue_review.digest(p) for p in work.iterdir() if p.is_file()},
                cues=rows,recognition=original['recognition'],
                diagnostic_review_origin='Saved live ASR/MT, explicit budgeted wording; evaluator-selected takes, human approval pending')
            store.save(manifest)
            report['review_manifest'] = str(work / 'review.json')
            output = cue_review.operate(store,pipe,identifier,1,'render',None,settings,
                lambda percent,message: print(percent,message,flush=True))
            run_process(['ffmpeg','-v','error','-nostdin','-i',output,'-f','null','-'],capture_output=True,check=True,timeout=180)
            report.update(output=output,output_sha256=cue_review.digest(output),full_decode_pass=True,
                all_14_measured_fit=True,freshly_generated_takes=13,retained_reviewed_takes=1,
                duration_seconds=pipe.get_duration(output),completed=True)
            preview = folder / 'SPLIT_PASSAGE_REVIEW_1m08_to_1m30.mp4'
            run_process(['ffmpeg','-v','error','-nostdin','-y','-ss','68','-i',output,'-t','22',
                '-map','0:v:0','-map','0:a:0','-c:v','libx264','-preset','veryfast','-crf','18',
                '-c:a','aac',str(preview)],check=True,timeout=180)
            run_process(['ffmpeg','-v','error','-nostdin','-i',str(preview),'-f','null','-'],capture_output=True,check=True,timeout=120)
            report.update(preview=str(preview),preview_sha256=cue_review.digest(preview),preview_source_offset_seconds=68)
            assert cue_review.digest(ROOT / 'models.json') == registry_hash
            assert cue_review.digest(tts.profile_path) == profile_hash
            assert cue_review.digest(source) == raw['source_sha256']
            report['source_registry_profile_unchanged'] = True
    except Exception as exc:
        report.update(error=str(exc),error_type=type(exc).__name__,completed=False)
        raise
    finally:
        with bind_job(job):
            tts.release()
        job.cleanup()
        report.update(workspace_removed=not job.workspace.exists(),elapsed_seconds=round(time.monotonic()-started,3))
        receipt = folder.with_suffix('.json')
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(receipt,flush=True)


if __name__ == '__main__':
    main()
