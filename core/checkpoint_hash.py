"""Dependency-free verification usable in isolated inference workers."""
import hashlib
from pathlib import Path

MUSE_PARSER_SHA256 = {
    '79999_iter.pth': '468e13ca13a9b43cc0881a9f99083a430e9c0a38abd935431d1c28ee94b26567',
    'resnet18-5c106cde.pth': '5c106cde386e87d4033832f2996f5493238eda96ccf559d1d62760c4de0613f8',
}
MUSE_FACE_SHA256 = {
    's3fd-619a316812.pth': '619a31681264d3f7f7fc7a16a42cbbe8b23f31a256f75a366e5a1bcd59b33543',
    '2DFAN4-11f355bf06.pth.tar': '11f355bf0693120222f5955ce3f9dc8fb5763ebb30a47d7906e509490d32e4aa',
}


def require_asset_hash(path, expected, check=None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            if check:
                check()
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise RuntimeError('Model asset checksum mismatch: ' + str(path))
