"""Owned loopback UI transport with bounded, explicit shutdown.

Implements pywebview's server extension protocol. Browser preconnect sockets are
not application jobs and must never keep the interpreter alive after UI close.
"""
import json
import mimetypes
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
import threading
import time
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
import uuid
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server


class RequestServer(ThreadingMixIn,WSGIServer):
    daemon_threads=True
    block_on_close=False

    def get_request(self):
        connection,address=super().get_request()
        connection.settimeout(5)
        return connection,address

    def process_request_thread(self,*args):
        threading.current_thread().name='reflow-ui-request'
        super().process_request_thread(*args)


class QuietHandler(WSGIRequestHandler):
    def log_message(self,*args):
        pass


class DesktopServer:
    def __init__(self):
        self.uid=uuid.uuid4().hex
        self.js_callback={}
        self.running=False

    @property
    def is_running(self):
        return self.running

    @classmethod
    def start_server(cls,urls,http_port=None,keyfile=None,certfile=None,**kwargs):
        if keyfile or certfile:
            raise RuntimeError('Desktop transport supports loopback HTTP only')
        paths=[]
        for url in urls:
            if not isinstance(url,str):
                raise RuntimeError('Desktop transport requires local interface files')
            parsed=urlparse(url)
            if parsed.scheme not in ('','file') or parsed.netloc not in ('','localhost'):
                raise RuntimeError('Desktop transport requires local interface files')
            file=Path(url2pathname(parsed.path)).resolve()
            paths.append(file)
        if not paths:
            raise RuntimeError('Desktop transport requires an interface file')
        root=paths[0].parent if paths[0].is_file() else paths[0]
        if any(not file.is_relative_to(root) for file in paths):
            raise RuntimeError('Desktop windows must share their interface folder')
        server=cls()
        server.root_path=str(root)
        cls.common_path=urls[0].rsplit('/',1)[0] if paths[0].is_file() else urls[0]
        server.httpd=make_server('127.0.0.1',http_port or 0,server.handle,
                                server_class=RequestServer,handler_class=QuietHandler)
        server.port=server.httpd.server_port
        server.address=f'http://127.0.0.1:{server.port}/'
        server.js_api_endpoint=server.address+'js_api/'+server.uid
        server.running=True
        server.thread=threading.Thread(target=server.httpd.serve_forever,
                                       name='reflow-ui-server',daemon=True)
        server.thread.start()
        return server.address,cls.common_path,server

    def handle(self,environ,start_response):
        path=unquote(environ.get('PATH_INFO','/'))
        method=environ.get('REQUEST_METHOD','GET')
        status='404 Not Found';body=b'Not found';kind='text/plain; charset=utf-8'
        if path=='/js_api/'+self.uid and method=='POST':
            origin=environ.get('HTTP_ORIGIN')
            if origin and origin!=self.address.rstrip('/'):
                status='403 Forbidden';body=b'Origin rejected'
            else:
                try:
                    length=int(environ.get('CONTENT_LENGTH') or 0)
                    if not 0<length<=65536:
                        raise ValueError('Invalid request length')
                    data=json.loads(environ['wsgi.input'].read(length))
                    callback=self.js_callback.get(data['uid'])
                    if not callable(callback):
                        raise ValueError('Unknown callback')
                    body=json.dumps(callback(data)).encode('utf-8')
                    status='200 OK';kind='application/json'
                except (ValueError,KeyError,TypeError):
                    status='400 Bad Request';body=b'Invalid bridge request'
        elif method in ('GET','HEAD'):
            file=(Path(self.root_path)/(path.lstrip('/') or 'index.html')).resolve()
            if file.is_relative_to(Path(self.root_path)) and file.is_file():
                body=file.read_bytes();status='200 OK'
                kind=mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        headers=[('Content-Type',kind),('Content-Length',str(len(body))),
                 ('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]
        start_response(status,headers)
        return [b'' if method=='HEAD' else body]

    def stop(self):
        if not self.running:
            return
        self.running=False
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('Desktop UI server did not stop')


def cocoa_evaluator(dispatch,timeout=15):
    """Pinned Cocoa adapter: cancel JS return waits once their window is gone."""
    def evaluate(native,script,parse_json):
        done=threading.Event()
        result={'value':None,'error':None}
        def handler(value,error):
            if parse_json and value:
                try:
                    value=json.loads(value)
                except (ValueError,TypeError):
                    pass
            result['value']=value
            done.set()
        def invoke():
            if native.closed.is_set() or native.webview is None:
                done.set()
                return
            try:
                native.webview.evaluateJavaScript_completionHandler_(script,handler)
            except Exception as error:
                result['error']=error
                done.set()
        if native.closed.is_set() or native.webview is None:
            return None
        dispatch(invoke)
        deadline=time.monotonic()+timeout
        while not done.wait(.05):
            if native.closed.is_set() or native.webview is None:
                return None
            if time.monotonic()>=deadline:
                raise TimeoutError('Cocoa JavaScript evaluation did not complete')
        if result['error'] is not None:
            raise result['error']
        return result['value']
    evaluate._reflow_close_aware=True
    return evaluate


def install_cocoa_lifecycle():
    from importlib.metadata import version
    if version('pywebview')!='6.2.1':
        raise RuntimeError('Review the Cocoa lifecycle adapter for the installed pywebview version')
    from webview.platforms import cocoa
    if not getattr(cocoa.BrowserView.evaluate_js,'_reflow_close_aware',False):
        cocoa.BrowserView.evaluate_js=cocoa_evaluator(cocoa.AppHelper.callAfter)


def start_desktop(webview,*args,**kwargs):
    if sys.platform!='darwin':
        return webview.start(*args,**kwargs)
    install_cocoa_lifecycle()
    from webview import http
    try:
        return webview.start(*args,server=DesktopServer,**kwargs)
    finally:
        server=http.global_server
        if isinstance(server,DesktopServer):
            server.stop()
            http.global_server=None
