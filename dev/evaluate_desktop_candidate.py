"""Actual candidate acceptance with disposable state; no model/API downloads."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation'
PYTHON = ROOT / 'runtime_profiles/desktop-candidate/python.exe'
CODE = r'''
import base64,hashlib,importlib,importlib.metadata as metadata,importlib.util,json,math,os,sys,time,types,uuid
from pathlib import Path
root,scratch,phase=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
sys.path[:0]=[str(root),str(root/'core')]
os.environ.update(REFLOW_OFFLINE='1',PATH=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH',''))
config=types.ModuleType('config');config.__file__=str(scratch/'config.py');sys.modules['config']=config
exec(compile((root/'config.py').read_text(encoding='utf-8'),config.__file__,'exec'),config.__dict__)
report={'passed':False,'checks':{},'phase':phase,'models_downloaded':False,'native_window_tested':phase.startswith('native')}
def check(name,value):
    report['checks'][name]=bool(value)
    if not value:raise AssertionError(name)
try:
    if phase=='backend':
        from packaging.utils import canonicalize_name
        from packaging.requirements import Requirement
        lock=json.loads((root/'docs/validation/2026-10-13-desktop-candidate-lock-review.json').read_text())
        expected={p['name']:p['version'] for p in lock['packages']}
        installed={}
        for dist in metadata.distributions():
            name=canonicalize_name(dist.metadata['Name'])
            check('unique_metadata_'+name,name not in installed)
            installed[name]=dist.version
        check('exact_installed_closure',installed==expected)
        for row in lock['packages']:
            dist=metadata.distribution(row['name'])
            check('origin_'+row['name'],Path(dist.locate_file('')).resolve().is_relative_to(root/'runtime_profiles/desktop-candidate'))
        check('python313',sys.version_info[:3]==(3,13,16))
        check('no_legacy_torch',importlib.util.find_spec('torch') is None and config.DEVICE=='cpu')
        for module in ['webview','pystray','PIL','psutil','pydub','requests','filelock','packaging','keyring','tqdm','soundfile','numpy','cffi','proxy_tools']:
            imported=importlib.import_module(module)
            check('import_'+module,Path(imported.__file__).resolve().is_relative_to(root/'runtime_profiles/desktop-candidate'))
        import clr
        clr.AddReference('System.Windows.Forms')
        from System.Windows.Forms import Form
        check('native_winforms_loaded',Form is not None)
        import numpy as np,soundfile as sf
        audio=np.sin(2*np.pi*440*np.arange(24000)/24000).astype('float32')*.1
        wave=scratch/'tone.wav';sf.write(wave,audio,24000)
        decoded,rate=sf.read(wave)
        check('native_audio_roundtrip',rate==24000 and len(decoded)==24000 and np.max(np.abs(decoded-audio))<.0001)
        from core.audio_utils import load_speech_audio
        check('pydub_audioop_decode',len(load_speech_audio(str(wave)))==1000)
        import keyring
        service='ReflowStudioDesktopCandidateTest';key='owned-'+uuid.uuid4().hex
        try:
            keyring.set_password(service,key,'disposable-test-value')
            check('native_credential_roundtrip',keyring.get_password(service,key)=='disposable-test-value')
        finally:
            keyring.delete_password(service,key)
        import main
        from bridge.api import PythonBridge
        bridge=PythonBridge()
        check('desktop_integrity',bridge.run_integrity_check()['ok'])
        check('four_pipeline_templates',len(bridge.list_pipeline_templates())==4)
        check('language_choices',len(bridge.list_languages())>=10 and len(bridge.list_source_languages())>=10)
        check('graph_loaded',len(bridge.get_graph_definition()['nodes'])>=5)
        bridge.update_settings({'default_language':'hi','xtts_runtime':'isolated'})
        bridge.update_ui_preferences({'reflow-theme':'light'})
        from core.settings import Settings
        check('settings_persist',Settings().get('default_language')=='hi')
        check('ui_preferences_persist',bridge.get_ui_preferences()['reflow-theme']=='light')
        check('fresh_models_empty',bridge.list_models()==[])
        from pipeline import ReflowPipeline
        source=scratch/'input.srt';source.write_text('1\n00:00:00,000 --> 00:00:02,000\nHello world.\n\n')
        events=list(ReflowPipeline().process_subtitle_translate_gen(str(source),'source','en'))
        check('subtitle_export',events[-1][0]==100 and 'Hello world.' in Path(events[-1][2]).read_text())
        from core.runtime_checks import preflight
        try:preflight(None,dict(lang='source',keep_bg=False,xtts_runtime='isolated'),'audio_dub')
        except RuntimeError as error:check('missing_default_stt_reported','faster_whisper' in str(error))
        else:check('missing_default_stt_reported',False)
    elif phase.startswith('native'):
        import webview
        from bridge.api import PythonBridge
        bridge=PythonBridge()
        bridge.update_ui_preferences({'reflow.tourComplete':'true','reflow-experience-level':'expert'})
        if phase=='native-controls-ready':
            bridge.update_settings({'onboarding_complete':True})
        window=webview.create_window('Reflow candidate acceptance',(root/'frontend/dist/index.html').as_uri(),
            js_api=bridge,hidden=True,width=1200,height=800)
        def evaluate():
            try:
                deadline=time.monotonic()+45
                while time.monotonic()<deadline:
                    ready=window.evaluate_js('Boolean(window.pywebview && window.pywebview.api && document.querySelector("#root") && document.querySelector("#root").textContent.length>30)')
                    if ready:break
                    time.sleep(.2)
                check('frontend_mounted_with_bridge',bool(ready))
                window.evaluate_js("(async()=>{try{const a=window.pywebview.api;window.__candidateResult={languages:await a.list_languages(),templates:await a.list_pipeline_templates(),settings:await a.get_settings(),integrity:await a.run_integrity_check()};}catch(e){window.__candidateResult={error:String(e)};}})()")
                while time.monotonic()<deadline:
                    value=window.evaluate_js('window.__candidateResult || null')
                    if value:break
                    time.sleep(.2)
                check('javascript_bridge_calls',isinstance(value,dict) and not value.get('error'))
                check('javascript_templates',len(value['templates'])==4)
                check('javascript_settings',value['settings']['values']['xtts_runtime']=='legacy')
                check('javascript_integrity',value['integrity']['ok'])
                if phase.startswith('native-controls'):
                    if phase=='native-controls-ready':
                        time.sleep(1)
                        check('onboarding_overlay_absent',window.evaluate_js('!document.querySelector("#root").textContent.includes("WELCOME TO REFLOW STUDIO")'))
                    for page in ['dashboard','nodes','assets','marketplace','logs','settings']:
                        clicked=window.evaluate_js(f'(()=>{{const b=document.querySelector("[data-tour=nav-{page}]");if(!b)return false;b.click();return true;}})()')
                        check('navigation_present_'+page,clicked)
                        time.sleep(.4)
                        check('navigation_active_'+page,window.evaluate_js(f'document.querySelector("[data-tour=nav-{page}]").classList.contains("text-primary")'))
                    check('xtts_selector_rendered',window.evaluate_js('document.querySelector("#root").textContent.includes("XTTS speech runtime")'))
                    opened=window.evaluate_js('(()=>{const s=Array.from(document.querySelectorAll("span")).find(e=>e.textContent==="XTTS speech runtime");const b=s?.parentElement.querySelector("button[role=combobox]");if(!b)return false;b.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,button:0,ctrlKey:false,pointerType:"mouse"}));return true;})()')
                    check('xtts_selector_opened',opened)
                    time.sleep(.3)
                    selected=window.evaluate_js('(()=>{const o=Array.from(document.querySelectorAll("[role=option]")).find(e=>e.textContent.includes("Isolated CPU runtime"));if(!o||o.getAttribute("aria-disabled")==="true")return false;o.dispatchEvent(new PointerEvent("pointerup",{bubbles:true,button:0,pointerType:"mouse"}));o.click();return true;})()')
                    check('isolated_option_enabled_and_selected',selected)
                    time.sleep(.8)
                    window.evaluate_js('(async()=>{window.__candidateSelected=(await window.pywebview.api.get_settings()).values.xtts_runtime;})()')
                    time.sleep(.4)
                    check('selector_saved_through_real_bridge',window.evaluate_js('window.__candidateSelected')=='isolated')
                report['frontend_text_excerpt']=window.evaluate_js('document.querySelector("#root").textContent.slice(0,160)')
                report['gui_renderer']=window.gui.renderer
            except BaseException as error:report['error']=repr(error)
            finally:window.destroy()
        webview.start(evaluate,gui='edgechromium',debug=False,storage_path=str(scratch/'webview-storage'))
    report['passed']=bool(report['checks']) and all(report['checks'].values()) and 'error' not in report
except BaseException as error:
    report['error']=repr(error)
finally:
    (root/f'docs/validation/2026-10-14-desktop-candidate-{phase}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if not report['passed']:raise SystemExit(1)
'''


def main():
    phase = sys.argv[1]
    assert phase in {'backend', 'native', 'native-controls', 'native-controls-ready'}
    with tempfile.TemporaryDirectory(prefix='desktop-acceptance-', dir=ROOT / 'temp') as scratch:
        with (OUT / f'2026-10-14-desktop-candidate-{phase}.log').open('wb') as log:
            result = subprocess.run([str(PYTHON), '-B', '-X', 'utf8', '-c', CODE, str(ROOT), scratch, phase],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=180,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('Phase:', phase, 'exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
