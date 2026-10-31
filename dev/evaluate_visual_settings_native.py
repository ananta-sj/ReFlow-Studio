"""Reuse native settings harness for the explicit M2M100 fallback selector."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dev'))
from evaluate_desktop_candidate import CODE


def main():
    code=CODE.replace('XTTS speech runtime','Face enhancement runtime').replace('xtts_runtime','enhancement_runtime').replace('xtts_selector','enhancement_selector')
    rendered="                    check('enhancement_selector_rendered',window.evaluate_js('document.querySelector(\"#root\").textContent.includes(\"Face enhancement runtime\")'))"
    assert rendered in code
    code=code.replace(rendered,"""                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline and not window.evaluate_js('document.querySelector("#root").textContent.includes("Face enhancement runtime")'):time.sleep(.2)
"""+rendered)
    marker="                    check('selector_saved_through_real_bridge',window.evaluate_js('window.__candidateSelected')=='isolated')"
    before="                    time.sleep(.4)\n"+marker
    assert before in code
    code=code.replace(before,"""                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline and window.evaluate_js('window.__candidateSelected')!='isolated':
                        window.evaluate_js('(async()=>{if(window.__fallbackReadBusy)return;window.__fallbackReadBusy=true;try{window.__candidateSelected=(await window.pywebview.api.get_settings()).values.enhancement_runtime;}finally{window.__fallbackReadBusy=false;}})()')
                        time.sleep(.2)
"""+marker)
    code=code.replace('2026-10-14-desktop-candidate-{phase}.json','2026-10-16-visual-routing-native.json')
    with tempfile.TemporaryDirectory(prefix='visual-native-',dir=ROOT/'temp') as scratch:
        with (ROOT/'docs/validation/2026-10-16-visual-routing-native.log').open('wb') as log:
            result=subprocess.run([str(ROOT/'runtime_profiles/desktop-candidate/python.exe'),'-B','-X','utf8','-c',
                code,str(ROOT),scratch,'native-controls-ready'],stdout=log,stderr=subprocess.STDOUT,timeout=180,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    print('Native face enhancement settings exit:',result.returncode)
    return result.returncode


if __name__=='__main__':raise SystemExit(main())

