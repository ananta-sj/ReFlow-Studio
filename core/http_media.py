"""Bounded multipart uploads and atomic streamed media downloads."""
import io
import os
import re
import uuid

from core.render_context import check_cancelled

CHUNK_BYTES = 256 * 1024


def _quoted(value):
    return str(value).replace('\r', '%0D').replace('\n', '%0A').replace('"', '%22')


class MultipartBody:
    def __init__(self, data, files):
        boundary = uuid.uuid4().hex
        self.content_type = 'multipart/form-data; boundary=' + boundary
        self.parts = []
        fields = (data or {}).items() if isinstance(data, dict) or data is None else data
        for name, values in fields:
            for value in values if isinstance(values, (list, tuple)) else [values]:
                if value is None:
                    continue
                payload = value if isinstance(value, bytes) else str(value).encode('utf-8')
                header = f'--{boundary}\r\nContent-Disposition: form-data; name="{_quoted(name)}"\r\n\r\n'.encode('utf-8')
                self.parts.append((header, io.BytesIO(payload), 0, len(payload)))
        for name, value in files.items():
            if not isinstance(value, tuple) or len(value) not in (2, 3):
                raise ValueError('Media upload requires filename, binary stream and optional content type')
            filename, stream = value[:2]
            content_type = value[2] if len(value) == 3 else 'application/octet-stream'
            if '\r' in content_type or '\n' in content_type:
                raise ValueError('Invalid media content type')
            if isinstance(stream, (bytes, str)):
                stream = io.BytesIO(stream.encode('utf-8') if isinstance(stream, str) else stream)
            start = stream.tell()
            stream.seek(0, os.SEEK_END)
            length = stream.tell() - start
            stream.seek(start)
            filename = re.split(r'[/\\]', str(filename))[-1]
            header = (f'--{boundary}\r\nContent-Disposition: form-data; name="{_quoted(name)}"; '
                      f'filename="{_quoted(filename)}"\r\nContent-Type: {content_type}\r\n\r\n').encode('utf-8')
            self.parts.append((header, stream, start, length))
        self.ending = f'--{boundary}--\r\n'.encode('ascii')
        self.length = sum(len(header) + length + 2 for header, _, _, length in self.parts) + len(self.ending)

    def __len__(self):
        return self.length

    def __iter__(self):
        for header, stream, start, length in self.parts:
            check_cancelled()
            yield header
            stream.seek(start)
            remaining = length
            while remaining:
                check_cancelled()
                chunk = stream.read(min(CHUNK_BYTES, remaining))
                if not isinstance(chunk, bytes) or not chunk:
                    raise RuntimeError('Upload source changed or is not a binary stream')
                remaining -= len(chunk)
                yield chunk
            yield b'\r\n'
        check_cancelled()
        yield self.ending


def write_media(response, output_path, kinds, *, validate_output=None):
    from core.pipeline import _staged_output, _validate_media
    try:
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type or 'application/json' in content_type:
            raise RuntimeError('Remote service returned an error/document instead of media')
        expected = response.headers.get('Content-Length')
        if expected is not None:
            expected = int(expected)
            if expected < 0:
                raise RuntimeError('Invalid media Content-Length')
        received = 0
        with _staged_output(output_path) as pending:
            with open(pending, 'wb') as stream:
                for chunk in response.iter_content(chunk_size=CHUNK_BYTES):
                    check_cancelled()
                    if not chunk:
                        continue
                    if received == 0 and chunk[:256].lstrip().lower().startswith((b'<html', b'<!doctype html')):
                        raise RuntimeError('Remote service returned an HTML document instead of media')
                    stream.write(chunk)
                    received += len(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if not received or (expected is not None and not response.headers.get('Content-Encoding') and received != expected):
                raise RuntimeError('Remote media transfer was empty or truncated')
            _validate_media(pending, set(kinds))
            if validate_output is not None:
                validate_output(pending)
        return output_path
    finally:
        response.close()
