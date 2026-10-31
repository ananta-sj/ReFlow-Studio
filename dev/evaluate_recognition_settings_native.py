"""Actual hidden WebView2 recognition selector using disposable app state."""
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'dev'))
from evaluate_desktop_candidate import CODE


def main():
    label = sys.argv[1] if len(sys.argv)>1 else 'native'
    assert label.replace('-', '').isalnum()
    marker = "                    check('selector_saved_through_real_bridge',window.evaluate_js('window.__candidateSelected')=='isolated')"
    extra = r'''
                    check('recognition_selector_rendered',window.evaluate_js('document.querySelector("#root").textContent.includes("CPU recognition runtime")'))
                    opened=window.evaluate_js('(()=>{const s=Array.from(document.querySelectorAll("span")).find(e=>e.textContent==="CPU recognition runtime");const b=s?.parentElement.querySelector("button[role=combobox]");if(!b)return false;b.dispatchEvent(new PointerEvent("pointerdown",{bubbles:true,button:0,ctrlKey:false,pointerType:"mouse"}));return true;})()')
                    check('recognition_selector_opened',opened)
                    time.sleep(.3)
                    selected=window.evaluate_js('(()=>{const o=Array.from(document.querySelectorAll("[role=option]")).find(e=>e.textContent.includes("Isolated CPU runtime"));if(!o||o.getAttribute("aria-disabled")==="true")return false;o.dispatchEvent(new PointerEvent("pointerup",{bubbles:true,button:0,pointerType:"mouse"}));o.click();return true;})()')
                    check('recognition_isolated_option_enabled_and_selected',selected)
                    time.sleep(.8)
                    window.evaluate_js('(async()=>{window.__recognitionSelected=(await window.pywebview.api.get_settings()).values.recognition_runtime;})()')
                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline and window.evaluate_js('window.__recognitionSelected')!='isolated':
                        window.evaluate_js('(async()=>{if(window.__recognitionReadBusy)return;window.__recognitionReadBusy=true;try{window.__recognitionSelected=(await window.pywebview.api.get_settings()).values.recognition_runtime;}finally{window.__recognitionReadBusy=false;}})()')
                        time.sleep(.2)
                    check('recognition_selector_saved_through_real_bridge',window.evaluate_js('window.__recognitionSelected')=='isolated')
'''
    assert CODE.count(marker)==1
    code = CODE.replace(marker, marker+extra)
    before = "                    time.sleep(.4)\n"+marker
    after = """                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline and window.evaluate_js('window.__candidateSelected')!='isolated':
                        window.evaluate_js('(async()=>{if(window.__speechReadBusy)return;window.__speechReadBusy=true;try{window.__candidateSelected=(await window.pywebview.api.get_settings()).values.xtts_runtime;}finally{window.__speechReadBusy=false;}})()')
                        time.sleep(.2)
"""+marker
    assert before in code
    code = code.replace(before, after)
    rendered = "                    check('xtts_selector_rendered',window.evaluate_js('document.querySelector(\"#root\").textContent.includes(\"XTTS speech runtime\")'))"
    assert rendered in code
    code = code.replace(rendered, """                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline and not window.evaluate_js('document.querySelector("#root").textContent.includes("XTTS speech runtime")'):time.sleep(.2)
"""+rendered)
    code = code.replace("2026-10-14-desktop-candidate-{phase}.json", f'2026-10-16-recognition-routing-{label}.json')
    with tempfile.TemporaryDirectory(prefix='recognition-native-', dir=ROOT/'temp') as scratch:
        with (ROOT/f'docs/validation/2026-10-16-recognition-routing-{label}.log').open('wb') as log:
            result = subprocess.run([str(ROOT/'runtime_profiles/desktop-candidate/python.exe'), '-B', '-X', 'utf8', '-c',
                                     code, str(ROOT), scratch, 'native-controls-ready'],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=180,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('Native recognition settings exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
