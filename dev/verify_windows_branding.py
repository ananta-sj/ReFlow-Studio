"""Exercise the production window startup and inspect its real native icon."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import threading


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('application',type=Path)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    root=args.application.resolve()
    sys.path[:0]=[str(root),str(root/'core')]
    os.environ['PATH']=str(root/'ffmpeg/bin')+os.pathsep+os.environ.get('PATH','')
    import main as application
    import webview
    ready=threading.Event();windows=[]
    result=dict(passed=False,application=str(root),python=sys.executable,
                production_main_exercised=True,window_hidden_for_test=True)
    real_create=webview.create_window
    real_start=webview.start

    def create(*args,**kwargs):
        kwargs['hidden']=True
        window=real_create(*args,**kwargs)
        window.events.loaded += lambda:ready.set()
        windows.append(window)
        return window

    def inspect():
        try:
            if not ready.wait(60): raise RuntimeError('Production window did not finish loading')
            window=windows[0]
            from System import Action
            from System.Drawing import Icon
            from System.Drawing.Imaging import ImageFormat
            from System.IO import MemoryStream
            def icon_bytes(icon):
                bitmap=icon.ToBitmap();stream=MemoryStream()
                try:
                    bitmap.Save(stream,ImageFormat.Png)
                    return bytes(stream.ToArray())
                finally:
                    stream.Dispose();bitmap.Dispose()
            def check_native():
                expected=Icon(str(root/'assets/icon.ico'))
                try:
                    result['native_window_icon_matches_logo']=icon_bytes(window.native.Icon)==icon_bytes(expected)
                    result['window_has_taskbar_entry']=bool(window.native.ShowInTaskbar)
                finally: expected.Dispose()
            window.native.Invoke(Action(check_native))
            pointer=ctypes.c_void_p()
            get_id=ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
            get_id.argtypes=[ctypes.POINTER(ctypes.c_void_p)];get_id.restype=ctypes.c_long
            if get_id(ctypes.byref(pointer))!=0: raise RuntimeError('No explicit taskbar identity')
            try: result['app_user_model_id']=ctypes.wstring_at(pointer)
            finally:
                free=ctypes.windll.ole32.CoTaskMemFree
                free.argtypes=[ctypes.c_void_p];free.restype=None;free(pointer)
            result['icon_argument_matches_logo']=result['startup_icon']==str(root/'assets/icon.ico')
            result['logo_sha256']=hashlib.sha256((root/'assets/icon.ico').read_bytes()).hexdigest()
            result['passed']=all(result.get(name) for name in (
                'native_window_icon_matches_logo','window_has_taskbar_entry','icon_argument_matches_logo')) and result['app_user_model_id']==application.APP_USER_MODEL_ID
        except Exception as error:
            result['error']=str(error)
        finally:
            if windows: windows[0].destroy()

    def start(*args,**kwargs):
        result['startup_icon']=kwargs.get('icon')
        return real_start(inspect,gui='edgechromium',**kwargs)
    webview.create_window=create;webview.start=start
    try:
        with application.ApplicationLock(root): application.main()
    except Exception as error:
        result['error']=str(error)
    finally:
        webview.create_window=real_create;webview.start=real_start
        args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
