"""Reflow Studio entry point (pywebview + React).

Loads the built frontend/dist/index.html via a real file:// URI - no HTTP
server, no port, nothing network-reachable. The only way the page can reach
Python is through bridge.api.PythonBridge, registered below as the window's
js_api.

IMPORTANT: pywebview only skips its internal local HTTP server (bottle,
bound to 127.0.0.1 on a random port - see webview/util.py's is_local_url())
when the url passed to create_window() already starts with "file://". A
bare filesystem path still triggers that server. Always build the URL with
pathlib's as_uri(), never pass DIST_INDEX as a plain path - verified via
`Get-NetTCPConnection`/netstat that a bare-path load DOES open a loopback
port and a file:// URI load does not.
"""

import os
import shutil
import sys
from pathlib import Path

# Several handlers (TTS, Vision/NudeNet, Wav2Lip, ...) print emoji status
# lines. Windows' default console codepage is very often NOT UTF-8 (cp1252
# or an OEM codepage like 437, neither of which can encode e.g. U+23F3
# "hourglass" or U+1F441 "eye") - a plain print() of any of them then
# raises UnicodeEncodeError and crashes whatever's running, main process
# or subprocess worker alike. Reconfiguring this process's own stdio, and
# propagating PYTHONIOENCODING so every subprocess this app spawns
# (core/run_stt.py, `python -m demucs`, etc. - all inherit os.environ)
# starts up already in UTF-8 mode, fixes both at the actual source rather
# than stripping emoji everywhere. Found by real crashes, not assumed.
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Under a PyInstaller-frozen build, __file__ resolves inside the bundle's
# internal extraction path, not the folder the actual .exe (and the
# models/ffmpeg/gfpgan folders the user actually has) lives in - sys.frozen
# is PyInstaller's own documented way to detect this and use
# sys.executable's directory instead. config.py mirrors this same check.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# The portable embeddable Python's python310._pth restricts sys.path to its
# own interpreter directory - the project root has to be added explicitly
# before anything under it (bridge/, core/) can be imported. core/ itself
# is also added because several of its modules import each other with bare
# names (e.g. `from audio_separator import AudioSeparator`).
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "core"))

# frontend/dist is bundled as PyInstaller `datas` (packaging/reflow.spec),
# which land under sys._MEIPASS - PyInstaller's own extraction/resource dir
# (the onedir build's _internal/ folder) - NOT next to the .exe like the
# runtime asset folders (ffmpeg/models/gfpgan) that build_dist.py copies in
# separately. Conflating the two 404s the frontend in a packaged build.
if getattr(sys, "frozen", False):
    RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    RESOURCE_DIR = BASE_DIR


def _inject_portable_ffmpeg():
    """Prefer a system ffmpeg on PATH; fall back to a bundled ffmpeg/ folder
    for either the Windows (ffmpeg.exe) or Mac/Linux (ffmpeg) binary name."""
    if shutil.which("ffmpeg"):
        return
    for candidate_dir in (os.path.join(BASE_DIR, "ffmpeg", "bin"), os.path.join(BASE_DIR, "ffmpeg")):
        for binary in ("ffmpeg.exe", "ffmpeg"):
            if os.path.exists(os.path.join(candidate_dir, binary)):
                os.environ["PATH"] += os.pathsep + candidate_dir
                return


_inject_portable_ffmpeg()

import webview

from bridge.api import PythonBridge
from core.tray import TrayController
from core.application_lock import ApplicationLock, AlreadyRunning

DIST_INDEX = Path(RESOURCE_DIR) / "frontend" / "dist" / "index.html"

WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900  # 16:9 - the previous 1500x900 was actually 5:3 (1.667)
APP_USER_MODEL_ID = 'ReflowStudio.Desktop'


def _set_windows_app_id():
    """Group this window as Reflow instead of the bundled Python interpreter."""
    if sys.platform != 'win32':
        return False
    import ctypes
    function = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    function.argtypes = [ctypes.c_wchar_p]
    function.restype = ctypes.c_long
    result = function(APP_USER_MODEL_ID)
    if result != 0:
        raise OSError('Windows could not set the Reflow application identity: '+hex(result & 0xffffffff))
    return True


def _application_icon_path():
    filename = 'icon.ico' if sys.platform == 'win32' else 'icon.png'
    for folder in (RESOURCE_DIR, BASE_DIR):
        path = Path(folder) / 'assets' / filename
        if path.is_file():
            return str(path)
    return None


def _force_exact_window_size(window):
    """pywebview's initial_width/height (via WinForms' AutoScaleMode.Dpi +
    Size(int(w*scale), int(h*scale))) does not reliably produce the exact
    requested size on Windows - measured a window created with width=1600,
    height=900 actually landing at 1750x952 (ratios of 1.094 and 1.058,
    which rules out a plain DPI-scale explanation since a uniform scale
    would affect both dimensions equally). Rather than chase that WinForms
    quirk further, force the exact size via raw Win32 calls once the window
    exists, and center it on the primary monitor's work area."""
    if sys.platform != "win32":
        return

    import ctypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    hwnd = user32.FindWindowW(None, window.title)
    if not hwnd:
        return

    work_area = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0)  # SPI_GETWORKAREA
    work_w = work_area.right - work_area.left
    work_h = work_area.bottom - work_area.top

    x = work_area.left + max(0, (work_w - WINDOW_WIDTH) // 2)
    y = work_area.top + max(0, (work_h - WINDOW_HEIGHT) // 2)

    SWP_NOZORDER = 0x0004
    SWP_SHOWWINDOW = 0x0040
    user32.SetWindowPos(hwnd, None, x, y, WINDOW_WIDTH, WINDOW_HEIGHT, SWP_NOZORDER | SWP_SHOWWINDOW)


def main():
    if not DIST_INDEX.exists():
        raise SystemExit(
            f"Frontend build not found at {DIST_INDEX}.\n"
            f"Run: cd frontend && npm run build"
        )

    _set_windows_app_id()
    bridge = PythonBridge()
    window = webview.create_window(
        "Reflow Studio",
        url=DIST_INDEX.as_uri(),
        js_api=bridge,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(1200, 700),
        frameless=True,
        easy_drag=False,
    )
    window.events.shown += lambda: _force_exact_window_size(window)
    # Wired after window creation since the tray's "restore" action needs a
    # real Window instance - bridge.minimize_to_tray() is a no-op until this
    # runs, which is fine, it only happens after the window (and therefore
    # this assignment) already exists. Passes bound methods only, never the
    # TrayController itself - see PythonBridge.__init__'s docstring on
    # _minimize_to_tray_fn for why (pywebview recursively introspects every
    # non-callable attribute reachable from the bridge to build its JS API
    # surface, which would otherwise walk straight into the live WinForms
    # window object and its native COM proxies).
    tray = TrayController(window)
    bridge.set_tray_handlers(tray.minimize_to_tray, tray.stop)
    webview.start(icon=_application_icon_path())


if __name__ == "__main__":
    try:
        with ApplicationLock(BASE_DIR):
            main()
    except AlreadyRunning as error:
        print(str(error))
        raise SystemExit(1)
