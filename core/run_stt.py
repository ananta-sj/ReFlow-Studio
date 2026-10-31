import sys
import os
import json

# Windows' default console codepage often isn't UTF-8 - the emoji status
# prints below then raise UnicodeEncodeError and crash this worker before
# it ever transcribes anything. main.py sets PYTHONIOENCODING for the main
# process's own subprocess spawns, but this reconfigures directly too in
# case this script is ever invoked standalone (see main.py's fuller
# explanation of the same fix).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Add the 'core' folder to Python path so we can find stt_handler
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.dirname(current_dir))

from stt.stt_handler import STTHandler
from core.transcription import normalize_transcription

if __name__ == "__main__":
    video_path = sys.argv[1]
    json_output_path = sys.argv[2]
    model_size = sys.argv[3] if len(sys.argv) > 3 else "medium"

    print(f"[WORKER] 🛠️ Soldier started for: {video_path}")

    # We use CPU here to be 100% safe from GPU conflicts
    # Since this is a separate process, it won't crash the main app
    stt = STTHandler(device="cpu", model_size=model_size)
    source_language = sys.argv[4] if len(sys.argv) > 4 else 'auto'
    transcript = stt.transcribe(video_path, source_language=source_language)
    
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(normalize_transcription(transcript).to_payload(), f, ensure_ascii=False, indent=4)
        
    print("[WORKER] ✅ Mission Complete. Saving JSON.")
