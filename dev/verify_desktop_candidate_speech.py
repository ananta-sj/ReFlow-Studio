"""Reuse the accepted speech/cancel contract under the new desktop parent.

All changed locations are asserted once; disposable config/settings/job paths
replace the portable-copy paths, and historical evidence is never overwritten.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dev.verify_xtts_portable_trial import CODE


def main():
    injection = """root=Path(sys.argv[1]);source=Path(sys.argv[2]);scratch=Path(sys.argv[3]);sys.path[:0]=[str(root),str(root/'core')]
import types
config=types.ModuleType('config');config.__file__=str(scratch/'config.py');sys.modules['config']=config
exec(compile((root/'config.py').read_text(encoding='utf-8'),config.__file__,'exec'),config.__dict__)
"""
    changes = {
        "root=Path(sys.argv[1]);source=Path(sys.argv[2]);sys.path[:0]=[str(root),str(root/'core')]": injection,
        "job=RenderContext(root/'temp')": "job=RenderContext(scratch/'temp')",
        "settings_path=root/'settings.json';owned_settings=False": "settings_path=scratch/'settings.json';owned_settings=False",
        "report=dict(passed=False,checks={},native_ui_test=False,model_weights_copied=False)":
            "report=dict(passed=False,checks={},native_ui_test=False,model_weights_copied=False,parent_python=sys.executable)",
        "'imports_relocated'": "'parent_source_origin'",
        "'runtime_relocated'": "'isolated_worker_owned'",
        "2026-10-13-xtts-portable-trial-speech.wav": "2026-10-14-desktop-candidate-speech.wav",
        "not (root/'models/xtts/default').exists()": "not (root/'runtime_profiles/desktop-candidate/models').exists()",
        "2026-10-13-xtts-portable-trial-live.json": "2026-10-14-desktop-candidate-speech.json",
    }
    code = CODE
    for old, new in changes.items():
        assert code.count(old) == 1, 'Speech fixture changed; review before reuse: ' + old
        code = code.replace(old, new)
    with tempfile.TemporaryDirectory(prefix='desktop-speech-', dir=ROOT / 'temp') as scratch:
        with (ROOT / 'docs/validation/2026-10-14-desktop-candidate-speech.log').open('wb') as log:
            result = subprocess.run([str(ROOT / 'runtime_profiles/desktop-candidate/python.exe'), '-B', '-X', 'utf8',
                                     '-c', code, str(ROOT), str(ROOT), scratch], stdout=log, stderr=subprocess.STDOUT,
                                    timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('Speech/cancellation acceptance exit:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
