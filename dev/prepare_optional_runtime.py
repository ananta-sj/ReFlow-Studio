"""Build an isolated Windows embedded profile without changing the core runtime.

Run with an existing pip-capable Python. Package installation is explicit; the
profile interpreter never shares site-packages with that Python or the core.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "vision": ["nudenet==3.4.1", "numpy==1.26.4", "onnxruntime==1.20.1",
               "opencv-python-headless==4.10.0.84"],
    "f5": ["f5-tts==1.1.22", "numpy==1.26.4", "torch==2.9.1+cpu",
           "torchaudio==2.9.1+cpu", "torchcodec==0.8.1"],
    "musetalk": ["torch==2.7.1+cpu", "torchaudio==2.7.1+cpu", "torchvision==0.22.1+cpu",
                 "numpy==1.26.4", "diffusers==0.30.2", "transformers==4.39.2",
                 "huggingface-hub==0.36.2", "face-alignment==1.5.0", "librosa==0.11.0",
                 "soundfile==0.13.1", "omegaconf==2.3.0", "einops==0.8.1",
                 "opencv-python==4.10.0.84", "ffmpeg-python==0.2.0"],
}


def prepare(name):
    if name not in PROFILES:
        raise ValueError("Unknown profile")
    source = ROOT / "build" / "windows-portable"
    destination = ROOT / "runtime_profiles" / name
    if destination.exists():
        raise FileExistsError(f"Profile already exists; preserve it: {destination}")
    destination.mkdir(parents=True)
    for item in source.iterdir():
        if item.is_file() and (item.suffix.lower() in {".dll", ".pyd"} or
                              item.name in {"python.exe", "pythonw.exe", "python310.zip"}):
            shutil.copy2(item, destination / item.name)
    (destination / "Lib" / "site-packages").mkdir(parents=True)
    # The core keeps an old VC runtime under an .OLD name. Use the actual
    # DLL supplied with this matching installed Python, rather than relying
    # on a system-wide VC installation on the user's destination computer.
    vc_runtime = Path(sys._base_executable).parent / 'vcruntime140.dll'
    if not (destination / 'vcruntime140.dll').exists() and vc_runtime.is_file():
        shutil.copy2(vc_runtime, destination / 'vcruntime140.dll')
    (destination / "python310._pth").write_text(
        "python310.zip\n.\nLib/site-packages\nimport site\n", encoding="utf-8")
    (destination / "profile.json").write_text(json.dumps({
        "profile": name, "status": "prepared", "python": "3.10.11", "device": "cpu"}), encoding="utf-8")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Retry a previously prepared profile")
    args = parser.parse_args()
    if args.resume:
        destination = ROOT / "runtime_profiles" / args.profile
        metadata = json.loads((destination / "profile.json").read_text(encoding="utf-8"))
        if metadata.get("profile") != args.profile or metadata.get("status") != "prepared":
            raise ValueError("Only an unfinished prepared profile can be retried")
    else:
        destination = prepare(args.profile)
    report = destination / "package-install-report.json"
    if args.install:
        lock = ROOT / 'packaging' / 'optional' / (args.profile + '.lock.txt')
        package_arguments = ['--require-hashes', '-r', str(lock)] if lock.is_file() else PROFILES[args.profile]
        subprocess.run([sys.executable, "-m", "pip", "install", "--isolated",
                        "--disable-pip-version-check", "--no-cache-dir", "--no-compile",
                        "--only-binary=:all:",
                        "--no-binary=antlr4-python3-runtime,transformers-stream-generator,encodec",
                        "--ignore-installed", "--target",
                        str(destination / "Lib" / "site-packages"), "--report", str(report),
                        *(["--extra-index-url", "https://download.pytorch.org/whl/cpu"]
                          if args.profile != "vision" else []),
                        *package_arguments], check=True)
        result = json.loads(report.read_text(encoding="utf-8"))
        locked = sorted(f"{item['metadata']['name']}=={item['metadata']['version']}"
                        for item in result["install"])
        (destination / "requirements.lock.txt").write_text(
            "\n".join(locked) + "\n", encoding="utf-8")
        subprocess.run([str(destination / 'python.exe'), '-B',
                        str(ROOT / 'dev' / 'verify_optional_runtime.py'), args.profile], check=True)
    print(destination)


if __name__ == "__main__":
    main()
