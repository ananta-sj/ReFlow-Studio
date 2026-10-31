import ast
import json
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'core')]
changed = ['core/model_assets.py','core/integrity.py','core/tts/tts_handler.py',
           'core/lipsync_handler.py','core/enhancer.py','core/rvc/rvc_handler.py',
           'core/providers/lipsync/musetalk_local.py','dev/restore_models.py',
           'dev/cleanup_smoke.py','dev/test_model_assets.py','dev/run_cleanup_checks.py',
           'dev/verify_model_sources.py']
for relative in changed:
    ast.parse((root / relative).read_text(encoding='utf-8-sig'), filename=relative)

import main
clip = root / 'temp/cleanup-ffmpeg-smoke.mp4'
try:
    ffmpeg = root / 'ffmpeg/bin/ffmpeg.exe'
    ffprobe = root / 'ffmpeg/bin/ffprobe.exe'
    subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'testsrc=size=64x64:rate=10', '-t', '0.2', '-pix_fmt', 'yuv420p', '-y', str(clip)], check=True, timeout=30)
    info = json.loads(subprocess.check_output([str(ffprobe), '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(clip)], timeout=30))
    assert float(info['format']['duration']) > 0
    print(json.dumps({'syntax_files_checked': len(changed), 'main_import': 'ok', 'frontend_exists': main.DIST_INDEX.exists(),
                      'ffmpeg_encode': 'ok', 'ffprobe_codec': info['streams'][0]['codec_name'],
                      'duration_seconds': info['format']['duration']}, indent=2))
finally:
    clip.unlink(missing_ok=True)
