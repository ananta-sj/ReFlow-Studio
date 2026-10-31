"""System tray integration - lets the app be hidden from the taskbar
entirely while a render keeps running in the background, the same way
WinRAR can be minimized while it keeps zipping. The render thread
(bridge/api.py's start_render()) already doesn't care whether the window
is visible - this only changes what's on screen.

pywebview's Window.hide()/show() on the Windows (WinForms) backend map
directly to .NET Form.Hide()/Show() - a hidden top-level form has no
taskbar button at all, confirmed against pywebview's own winforms.py
source, so hide() alone (no separate "remove from taskbar" step) is
exactly the WinRAR-style behavior asked for.

pystray.Icon.run() blocks, so it's started on its own daemon thread
alongside pywebview's own main loop (main.py's webview.start()).
"""

import threading
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

_ICON_SIZE = 64
_ICON_COLOR = (200, 255, 77)  # matches frontend/src/index.css's --primary


def _build_icon_image():
    logo = Path(__file__).resolve().parents[1] / 'assets' / 'icon.png'
    if logo.is_file():
        with Image.open(logo) as image:
            return image.convert('RGBA')
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = 6
    draw.ellipse([pad, pad, _ICON_SIZE - pad, _ICON_SIZE - pad], fill=_ICON_COLOR)
    return img


class TrayController:
    def __init__(self, window):
        self.window = window
        self._icon = None
        self._notified = False

    def _restore(self, *_args):
        self.window.show()

    def _quit(self, *_args):
        if self._icon:
            self._icon.stop()
        self.window.destroy()

    def _build(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show Reflow Studio", self._restore, default=True),
            pystray.MenuItem("Quit", self._quit),
        )
        self._icon = pystray.Icon("reflow_studio", _build_icon_image(), "Reflow Studio", menu)

    def start(self):
        """Builds and runs the tray icon - safe to call once, up front, so
        it's already present the first time minimize_to_tray() is used."""
        if self._icon is not None:
            return
        self._build()
        threading.Thread(target=self._icon.run, daemon=True).start()

    def minimize_to_tray(self):
        self.start()
        self.window.hide()
        if not self._notified:
            self._notified = True
            try:
                self._icon.notify("Still running in the background - click this icon to reopen.", "Reflow Studio")
            except Exception:
                pass  # balloon notifications aren't supported on every OS/tray implementation

    def stop(self):
        if self._icon:
            self._icon.stop()
