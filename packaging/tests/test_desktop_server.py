"""Loopback UI server lifecycle: idle browser sockets must not hold exit open."""
import importlib.util
from pathlib import Path
import socket
import tempfile
import threading
import unittest
import urllib.request
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('desktop_server_test',ROOT/'core/desktop_server.py')
server_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(server_module)

class DesktopServerTests(unittest.TestCase):
    def test_static_ui_and_idle_browser_socket_close_without_non_daemon_thread(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'index.html';file.write_text('UI fixture')
            address,common,server=server_module.DesktopServer.start_server([file.as_uri()],None,None,None)
            import os
            self.assertEqual(os.path.relpath(file.as_uri(),common),'index.html')
            idle=socket.create_connection(('127.0.0.1',server.port),timeout=2)
            try:
                with urllib.request.urlopen(address+'index.html',timeout=2) as response:
                    self.assertEqual(response.read(),b'UI fixture')
                server.stop()
                self.assertFalse(server.thread.is_alive())
                self.assertFalse(server.is_running)
                self.assertTrue(all(t.daemon for t in threading.enumerate() if t.name.startswith('reflow-ui-request')))
            finally:
                idle.close();server.stop()

    def test_transport_rejects_traversal_and_cross_origin_bridge_calls(self):
        import json
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);ui=root/'ui';ui.mkdir()
            file=ui/'index.html';file.write_text('UI fixture')
            (root/'private.txt').write_text('private')
            address,_,server=server_module.DesktopServer.start_server([file.as_uri()])
            server.js_callback['window']=lambda data: dict(ok=True)
            try:
                with self.assertRaises(HTTPError) as error:
                    urllib.request.urlopen(address+'%2e%2e/private.txt',timeout=2)
                self.assertEqual(error.exception.code,404)
                request=urllib.request.Request(server.js_api_endpoint,data=json.dumps(dict(uid='window')).encode(),headers={'Origin':'https://untrusted.example'})
                with self.assertRaises(HTTPError) as error:
                    urllib.request.urlopen(request,timeout=2)
                self.assertEqual(error.exception.code,403)
                request=urllib.request.Request(server.js_api_endpoint,data=json.dumps(dict(uid='window')).encode(),headers={'Origin':address.rstrip('/')})
                with urllib.request.urlopen(request,timeout=2) as response:
                    self.assertEqual(json.loads(response.read()),dict(ok=True))
            finally:
                server.stop()

    def test_mac_transport_stops_on_desktop_error(self):
        from types import SimpleNamespace, ModuleType
        from unittest.mock import Mock, patch
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'index.html';file.write_text('fixture')
            _,_,server=server_module.DesktopServer.start_server([file.as_uri()])
            module=ModuleType('webview');module.http=SimpleNamespace(global_server=server)
            gui=SimpleNamespace(start=Mock(side_effect=RuntimeError('desktop fixture error')))
            with patch.object(server_module.sys,'platform','darwin'),patch.dict('sys.modules',{'webview':module}):
                with self.assertRaisesRegex(RuntimeError,'fixture error'):
                    server_module.start_desktop(gui)
            self.assertFalse(server.running)
            self.assertIsNone(module.http.global_server)

    def test_other_platforms_keep_existing_desktop_backend(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        gui=SimpleNamespace(start=Mock(return_value='normal desktop'))
        with patch.object(server_module.sys,'platform','win32'):
            self.assertEqual(server_module.start_desktop(gui,icon='fixture'),'normal desktop')
        gui.start.assert_called_once_with(icon='fixture')
