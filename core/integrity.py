import os
import sys
import subprocess
import importlib.util
import importlib
import requests
from tqdm import tqdm

class IntegrityDoctor:
    def __init__(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.core_dir = os.path.join(self.root_dir, "core")
        
        # Desktop imports; optional engines are checked for the selected job.
        self.critical_libs = {
            "webview": "pywebview",
            "pystray": "pystray",
            "PIL": "pillow",
            "psutil": "psutil",
            "pydub": "pydub",
            "requests": "requests",
            "filelock": "filelock",
            "packaging": "packaging",
            "keyring": "keyring",
            "tqdm": "tqdm",
        }
        self.engine_libs = {
            "torch": "torch",
            "basicsr": "basicsr",
            "gfpgan": "gfpgan",
            "librosa": "librosa",
            "scipy": "scipy",
            "numpy": "numpy",
            "tokenizers": "tokenizers",
        }

        # Critical Models
        self.critical_models = {
            os.path.join(self.core_dir, "Wav2Lip", "checkpoints", "Wav2Lip_GAN.pth"):
                "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth",
                
            os.path.join(self.root_dir, "gfpgan", "weights", "GFPGANv1.4.pth"): 
                "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
            
            os.path.join(self.root_dir, "gfpgan", "weights", "parsing_parsenet.pth"):
                "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth",
            
            os.path.join(self.root_dir, "gfpgan", "weights", "detection_Resnet50_Final.pth"):
                "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth",

            # THE MISSING FILE FIX:
            os.path.join(self.core_dir, "Wav2Lip", "face_detection", "ibug", "haarcascade_frontalface_alt.xml"):
                "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_alt.xml"
        }

    def install_package(self, package_name):
        print(f"   [+] Installing missing library: {package_name}...")
        try:
            if package_name == "basicsr":
                subprocess.check_call([sys.executable, "-m", "pip", "install", "setuptools<70.0.0", "wheel"])
                subprocess.check_call([sys.executable, "-m", "pip", "install", "basicsr==1.4.2", "--no-build-isolation"])
            else:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        except Exception as e:
            print(f"   [X] Failed to install {package_name}: {e}")

    def download_file(self, url, dest_path):
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        print(f"   [⬇] Downloading Asset: {os.path.basename(dest_path)}...")
        try:
            from core.downloader import download_with_progress
            for _ in download_with_progress(url, dest_path):
                pass
            return True
        except Exception as e:
            print(f"   [X] Download Failed: {e}")
            return False

    # --- THIS WAS MISSING IN YOUR LAST PASTE ---
    def check_libraries(self, include_engines=False):
        print("   [+] Checking Desktop Libraries...")
        failed = []
        libraries = dict(self.critical_libs)
        if include_engines:
            libraries.update(self.engine_libs)
        for import_name, pip_name in libraries.items():
            try:
                importlib.import_module(import_name)
            except Exception as error:
                failed.append({'module': import_name, 'package': pip_name, 'error': str(error)})
                print(f"   [!] UNAVAILABLE: {import_name}: {error}")
        return failed
    # -------------------------------------------

    def check_models(self):
        print("   [+] Checking AI Models...")
        failed = []
        for path, url in self.critical_models.items():
            if not os.path.exists(path) or os.path.getsize(path) < 1024:
                if not self.download_file(url, path):
                    failed.append(os.path.basename(path))

        if failed:
            print(f"   [!] {len(failed)} model(s) failed to download: {', '.join(failed)}")
            print("       The features that depend on them will not work until this is resolved.")
        return failed

    def run_all_checks(self, include_models=False, include_engines=False):
        print("--- RUNNING INTEGRITY CHECKS ---")
        libraries = self.check_libraries(include_engines=True) if include_engines else self.check_libraries()
        # Model weights are restored by the selected feature, not at UI launch.
        failed = self.check_models() if include_models else []
        print("--- CHECKS COMPLETE ---" if not failed and not libraries else "--- CHECKS COMPLETE (with warnings) ---")
        return {'ok': not failed and not libraries, 'unavailable_libraries': libraries, 'failed_models': failed}

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import argparse
    parser = argparse.ArgumentParser(description="Check runtime libraries without preloading model weights.")
    parser.add_argument("--download-models", action="store_true", help="Restore legacy Wav2Lip/GFPGAN assets now.")
    parser.add_argument("--include-engines", action="store_true", help="Also diagnose legacy shared AI imports; does not install packages.")
    args = parser.parse_args()
    result = IntegrityDoctor().run_all_checks(include_models=args.download_models, include_engines=args.include_engines)
    raise SystemExit(0 if result['ok'] else 1)
