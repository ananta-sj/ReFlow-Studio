"""Hidden desktop boot/bridge acceptance using a copied portable runtime."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('application', type=Path)
    parser.add_argument('report', type=Path)
    parser.add_argument('--all-pages', action='store_true')
    parser.add_argument('--cue-review', action='store_true')
    args = parser.parse_args()
    root = args.application.resolve()
    sys.path[:0] = [str(root), str(root / 'core')]
    os.environ['PATH'] = str(root / 'ffmpeg/bin') + os.pathsep + os.environ.get('PATH', '')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    import webview
    from bridge.api import PythonBridge
    report = {'acceptance': False, 'application': str(root), 'python': sys.executable,
              'visual_layout_reviewed': False}
    ready, response_ready = threading.Event(), threading.Event()
    started = time.monotonic()
    api = PythonBridge()
    if args.all_pages or args.cue_review:
        if root != Path(__file__).resolve().parents[1] / 'dist/portable-architecture-check':
            raise RuntimeError('Page-walk fixtures are restricted to the owned QA copy')
        api.settings.update({'onboarding_complete': True})
    fixture_id = ''
    if args.cue_review:
        from core.cue_review import ReviewStore, digest, configuration
        from core.pipeline import ReflowPipeline
        from pydub.generators import Sine
        import uuid
        fixture_id = uuid.uuid4().hex
        store = ReviewStore(root / 'outputs')
        folder = store.folder(fixture_id)
        folder.mkdir()
        for name, duration in [('source.wav', 2000), ('reference.wav', 1000), ('long.wav', 1500), ('fit.wav', 400)]:
            Sine(440).to_audio_segment(duration=duration).apply_gain(-12).export(folder / name, format='wav').close()
        manifest = dict(version=1, id=fixture_id, revision=1, name='QA synthetic cue review', created_at=time.time(),
            duration=2, target_lang='hi', speech_language='hi', source_language='en', actor='CLONED_USER', device='cpu',
            configuration=configuration(ReflowPipeline(), api.settings),
            assets={name: digest(folder / name) for name in ('source.wav', 'reference.wav')},
            cues=[dict(start=0, end=1, available_seconds=1, source_text='First source', text='पहली पंक्ति', accepted=None,
                       candidate=dict(file='long.wav', seconds=1.5, fits=False, sha256=digest(folder / 'long.wav'))),
                  dict(start=1, end=2, available_seconds=1, source_text='Second source', text='दूसरी पंक्ति', accepted=None,
                       candidate=dict(file='fit.wav', seconds=.4, fits=True, sha256=digest(folder / 'fit.wav')))])
        store.save(manifest)
    window = webview.create_window('Reflow portable acceptance',
        url=(root / 'frontend/dist/index.html').as_uri(), js_api=api, hidden=True)
    window.events.loaded += lambda: ready.set()

    def receive(result):
        report.update(result)
        response_ready.set()

    def inspect():
        try:
            if not ready.wait(45):
                raise RuntimeError('Desktop page did not load within 45 seconds')
            script = '''(async () => {
                const errors = [];
                window.__reflowAcceptance = {stage: 'bridge', errors};
                window.addEventListener('error', event => errors.push(String(event.message)));
                window.addEventListener('unhandledrejection', event => errors.push(String(event.reason)));
                const deadline = Date.now() + 30000;
                while (!window.pywebview?.api && Date.now() < deadline) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                if (!window.pywebview?.api) throw new Error('Python bridge missing');
                const settings = await window.pywebview.api.get_settings();
                window.__reflowAcceptance.stage = 'graph';
                const graph = await window.pywebview.api.get_graph_definition();
                window.__reflowAcceptance.stage = 'integrity';
                const integrity = await window.pywebview.api.run_integrity_check();
                while (!(document.getElementById('root')?.textContent?.length > 50) && Date.now() < deadline) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                const pages = {};
                window.__reflowAcceptance.pages = pages;
                if (CHECK_PAGES) {
                    window.__reflowAcceptance.stage = 'experience';
                    await new Promise(resolve => setTimeout(resolve, 2200));
                    const expert = [...document.querySelectorAll('[data-tour="experience-level"] button')]
                        .find(button => button.textContent.trim() === 'EXPERT');
                    if (!expert) throw new Error('Experience controls missing');
                    expert.click();
                    await new Promise(resolve => setTimeout(resolve, 300));
                    for (const page of ['dashboard', 'nodes', 'assets', 'marketplace', 'logs', 'settings']) {
                        window.__reflowAcceptance.stage = page;
                        const button = document.querySelector('[data-tour="nav-' + page + '"]');
                        if (!button) throw new Error('Navigation missing: ' + page);
                        button.click();
                        await new Promise(resolve => setTimeout(resolve, 1800));
                        pages[page] = {text_length: document.getElementById('root')?.textContent?.length ?? 0,
                                       selected: button.classList.contains('text-primary')};
                        if (page === 'nodes') pages[page].rendered_nodes = document.querySelectorAll('.react-flow__node').length;
                    }
                }
                let cueReview = null;
                if (CHECK_REVIEW) {
                    const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
                    const findButton = text => [...document.querySelectorAll('button')].find(button => button.textContent.trim() === text);
                    document.querySelector('[data-tour="nav-dashboard"]').click();
                    await wait(400);
                    const trigger = document.querySelector('[data-tour="dashboard-source"] button[role="combobox"]');
                    trigger.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true}));
                    await wait(300);
                    const option = [...document.querySelectorAll('[role="option"]')].find(item => item.textContent.includes('Audio -> Dubbed Audio'));
                    if (!option) throw new Error('Audio workflow option missing');
                    option.click();
                    await wait(800);
                    const reviewOption = document.querySelector('option[value="REVIEW_ID"]');
                    if (!reviewOption) throw new Error('Saved review missing');
                    const reviewSelect = reviewOption.parentElement;
                    if (reviewSelect.value !== 'REVIEW_ID') {
                        reviewSelect.value = 'REVIEW_ID';
                        reviewSelect.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                    const editorDeadline = Date.now() + 5000;
                    while (document.querySelectorAll('textarea').length !== 2 && Date.now() < editorDeadline) await wait(100);
                    if (document.querySelectorAll('textarea').length !== 2) throw new Error('Cue editors missing');
                    if (!findButton('Accept new take').disabled || !findButton('Render audio from accepted takes').disabled)
                        throw new Error('Overlong/unaccepted take can be rendered');
                    // Hidden scripted clicks are not trusted user gestures. Keep native
                    // decoding but bypass resume permission solely in this QA window.
                    const NativeAudioContext = window.AudioContext;
                    window.AudioContext = class extends NativeAudioContext {
                        resume() { return Promise.resolve(); }
                        createBufferSource() {
                            const node = super.createBufferSource();
                            const connect = node.connect.bind(node);
                            node.connect = destination => {
                                const gain = this.createGain(); gain.gain.value = 0;
                                gain.connect(destination); return connect(gain);
                            };
                            return node;
                        }
                    };
                    findButton('Listen to new take').click();
                    await wait(500);
                    if (!document.querySelector('[data-cue-player]')) throw new Error('Audio player missing');
                    findButton('Play preview').click();
                    const audioDeadline = Date.now() + 5000;
                    while (!document.querySelector('[data-cue-player]').textContent.includes('1.500 seconds') && Date.now() < audioDeadline) await wait(100);
                    const player = document.querySelector('[data-cue-player]');
                    if (!player.textContent.includes('1.500 seconds') || findButton('Stop preview').disabled)
                        throw new Error('Native audio decoding failed: ' + player.textContent);
                    findButton('Stop preview').click();
                    await wait(100);
                    if (!findButton('Stop preview').disabled) throw new Error('Preview stop failed');
                    const lineSelect = [...document.querySelectorAll('select')].find(item => item !== reviewSelect);
                    lineSelect.value = '1'; lineSelect.dispatchEvent(new Event('change', {bubbles: true}));
                    await wait(200);
                    if (findButton('Accept new take').disabled) throw new Error('Fitting take cannot be accepted');
                    findButton('Accept new take').click();
                    await wait(400);
                    let saved = await window.pywebview.api.get_cue_review('REVIEW_ID');
                    if (!saved.review.cues[1].accepted?.fits) throw new Error('Acceptance not persisted');
                    lineSelect.value = '0'; lineSelect.dispatchEvent(new Event('change', {bubbles: true}));
                    await wait(200);
                    const editor = document.querySelectorAll('textarea')[1];
                    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(editor, 'सुधारी गई पंक्ति');
                    editor.dispatchEvent(new Event('input', {bubbles: true}));
                    await wait(150);
                    if (findButton('Save changes').disabled || !lineSelect.disabled) throw new Error('Unsaved edits are not guarded');
                    findButton('Save changes').click();
                    await wait(400);
                    saved = await window.pywebview.api.get_cue_review('REVIEW_ID');
                    if (saved.review.cues[0].text !== 'सुधारी गई पंक्ति' || saved.review.cues[0].candidate || !saved.review.cues[1].accepted)
                        throw new Error('Cue edit did not invalidate only the edited take');
                    if (!findButton('Render audio from accepted takes').disabled) throw new Error('Incomplete review can render');
                    cueReview = {acceptance: true, editors: 2, native_decoded_audio_seconds: 1.5,
                        audible_playback_tested: false, resume_permission_bypassed_for_hidden_test: true,
                        stop_verified: true, overlong_take_blocked: true, acceptance_persisted: true,
                        edit_isolated: true, incomplete_render_blocked: true};
                }
                return {bridge_ready: true, settings_loaded: !!settings,
                    graph_nodes: graph.nodes?.length ?? 0, integrity_ok: integrity.ok,
                    rendered_text_length: document.getElementById('root')?.textContent?.length ?? 0,
                    pages, cue_review: cueReview, javascript_errors: errors};
            })().catch(error => ({javascript_failure: String(error), diagnostic: window.__reflowAcceptance}))'''
            window.evaluate_js(script.replace('CHECK_PAGES', 'true' if args.all_pages else 'false')
                .replace('CHECK_REVIEW', 'true' if args.cue_review else 'false').replace('REVIEW_ID', fixture_id), receive)
            if not response_ready.wait(60):
                report['diagnostic'] = window.evaluate_js('window.__reflowAcceptance')
                raise RuntimeError('Desktop bridge verification did not respond')
            if not report.get('integrity_ok') or not report.get('graph_nodes') or report.get('rendered_text_length', 0) <= 50:
                raise RuntimeError('Portable UI/bridge acceptance failed: ' + str(report))
            if args.all_pages and (report.get('javascript_errors') or len(report.get('pages', {})) != 6 or
                    any(not page['selected'] or page['text_length'] <= 150 for page in report['pages'].values()) or
                    report['pages']['nodes'].get('rendered_nodes') != report['graph_nodes']):
                raise RuntimeError('Portable page/graph acceptance failed: ' + str(report))
            if args.cue_review and (not report.get('cue_review', {}).get('acceptance') or report.get('javascript_errors')):
                raise RuntimeError('Cue review UI acceptance failed: ' + str(report))
            report['acceptance'] = True
        except Exception as exc:
            report['error'] = str(exc)
        finally:
            window.destroy()

    try:
        webview.start(inspect, gui='edgechromium')
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['acceptance'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
