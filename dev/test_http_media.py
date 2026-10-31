import hashlib
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from core.http_media import CHUNK_BYTES, MultipartBody, write_media
from core.providers.cloud_rest_common import request
from core.render_context import RenderContext, RenderCancelled, bind_job


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b'\0\0' * 1600)
    return output.getvalue()


class ObservedStream(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class HTTPMediaTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.output = self.root / 'output.wav'
        self.output.write_bytes(b'previous artifact')

    def response(self, chunks, length=None, content_type='audio/wav'):
        response = Mock()
        response.headers = {'Content-Type': content_type}
        if length is not None:
            response.headers['Content-Length'] = str(length)
        response.iter_content.return_value = iter(chunks)
        return response

    def test_upload_has_exact_length_bounded_reads_and_private_filename(self):
        stream = ObservedStream(b'x' * (3 * CHUNK_BYTES + 17))
        body = MultipartBody({'model': ['one', 'two'], 'unused': None},
                             {'file': ('C:\\private folder\\clip.wav', stream, 'audio/wav')})
        first = b''.join(body)
        self.assertEqual(len(first), len(body))
        self.assertEqual(first, b''.join(body))
        self.assertTrue(all(0 < size <= CHUNK_BYTES for size in stream.read_sizes))
        self.assertIn(b'filename="clip.wav"', first)
        self.assertNotIn(b'private folder', first)
        self.assertNotIn(b'name="unused"', first)

    def test_upload_header_injection_is_escaped(self):
        body = b''.join(MultipartBody({}, {'file': ('clip"\r\nInjected: yes.wav', io.BytesIO(b'x'), 'audio/wav')}))
        self.assertIn(b'clip%22%0D%0AInjected: yes.wav', body)
        self.assertNotIn(b'\r\nInjected:', body)

    def test_cancelled_upload_stops_before_next_payload_chunk(self):
        job = RenderContext(self.root)
        try:
            with bind_job(job):
                iterator = iter(MultipartBody({}, {'file': ('clip.wav', io.BytesIO(b'x' * CHUNK_BYTES), 'audio/wav')}))
                next(iterator)
                job.request_stop()
                with self.assertRaises(RenderCancelled):
                    next(iterator)
        finally:
            job.cleanup()

    def test_truncated_download_preserves_prior_bytes_and_closes_response(self):
        response = self.response([b'abc'], length=9)
        with self.assertRaisesRegex(RuntimeError, 'truncated'):
            write_media(response, str(self.output), {'audio'})
        self.assertEqual(self.output.read_bytes(), b'previous artifact')
        response.close.assert_called_once()
        self.assertEqual(list(self.root.glob('.reflow-*')), [])

    def test_html_response_is_never_published(self):
        response = self.response([b'<html>error</html>'])
        with self.assertRaisesRegex(RuntimeError, 'HTML'):
            write_media(response, str(self.output), {'audio'})
        self.assertEqual(self.output.read_bytes(), b'previous artifact')
        response.close.assert_called_once()

    def test_invalid_media_preserves_prior_output(self):
        response = self.response([b'garbage'], length=7)
        with self.assertRaises(RuntimeError):
            write_media(response, str(self.output), {'audio'})
        self.assertEqual(self.output.read_bytes(), b'previous artifact')

    def test_cancelled_download_discards_staging(self):
        job = RenderContext(self.root)
        response = self.response([])
        def chunks(**kwargs):
            yield wav_bytes()[:100]
            job.request_stop()
            yield wav_bytes()[100:]
        response.iter_content.side_effect = chunks
        try:
            with bind_job(job), self.assertRaises(RenderCancelled):
                write_media(response, str(self.output), {'audio'})
            self.assertEqual(self.output.read_bytes(), b'previous artifact')
            self.assertEqual(list(self.root.glob('.reflow-*')), [])
            response.close.assert_called_once()
        finally:
            job.cleanup()

    def test_http_error_closes_unconsumed_response(self):
        response = Mock(status_code=404)
        response.raise_for_status.side_effect = requests.HTTPError('not found')
        with patch.dict(os.environ, {'REFLOW_OFFLINE': '0'}), patch('requests.request', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'not found'):
                request('GET', 'https://example.invalid/output')
        response.close.assert_called_once()

    def test_actual_loopback_upload_and_streamed_audio_publication(self):
        received = {}
        audio = wav_bytes()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                remaining = int(self.headers['Content-Length'])
                received['length'] = remaining
                received['chunked'] = self.headers.get('Transfer-Encoding')
                digest, prefix, total = hashlib.sha256(), b'', 0
                while remaining:
                    chunk = self.rfile.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        break
                    prefix += chunk[:max(0, 400 - len(prefix))]
                    digest.update(chunk)
                    remaining -= len(chunk)
                    total += len(chunk)
                received.update(total=total, prefix=prefix, sha256=digest.hexdigest())
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Content-Length', str(len(audio)))
                self.end_headers()
                self.wfile.write(audio)

            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = ObservedStream(b'x' * (2 * CHUNK_BYTES + 17))
            with patch.dict(os.environ, {'REFLOW_OFFLINE': '1'}):
                response = request('POST', f'http://127.0.0.1:{server.server_port}/convert',
                    data={'model': 'fixture'}, files={'file': ('C:\\private\\clip.wav', payload, 'audio/wav')})
                self.assertEqual(write_media(response, str(self.output), {'audio'}), str(self.output))
            self.assertEqual(self.output.read_bytes(), audio)
            self.assertEqual(received['total'], received['length'])
            self.assertIsNone(received['chunked'])
            self.assertNotIn(b'private', received['prefix'])
            self.assertTrue(all(0 < size <= CHUNK_BYTES for size in payload.read_sizes))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)
