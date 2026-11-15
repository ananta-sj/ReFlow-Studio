"""Verified audio recovery files kept outside temporary render workspaces."""
import json
import logging
import os
import sys
from pathlib import Path
import tempfile
import threading
import wave

from core.render_context import check_cancelled, RenderCancelled
from core.run_manifest import _publish_bytes, file_identity
from core.stage_checkpoints import digest, safe_path, tree_identity


class AudioCheckpoints:
    def __init__(self, checkpoints, settings):
        self.checkpoints = checkpoints
        self.root = checkpoints.root / 'audio'
        self.project = checkpoints.project_root
        self.settings = settings
        self.lock = threading.RLock()
        self.fingerprints = {}

    def fingerprint(self, path):
        path = safe_path(path)
        info = path.stat()
        identity = (str(path), info.st_size, info.st_mtime_ns)
        with self.lock:
            if identity not in self.fingerprints:
                from core.stage_checkpoints import environment_identity
                self.fingerprints[identity] = (environment_identity(path) if path.is_dir() and path.name == 'site-packages'
                                               else tree_identity(path) if path.is_dir()
                                               else file_identity(path)['sha256'])
            return self.fingerprints[identity]

    def key(self, stage, inputs, provider=None, actor=None):
        if not self.checkpoints.code_unchanged():
            return None
        try:
            files = {
                'extract': ['core/audio_checkpoints.py', 'core/media_io.py'],
                'separate': ['core/audio_checkpoints.py', 'core/audio_separator.py', 'core/run_demucs.py',
                             'core/separation_runtime.py'],
                'speech': ['core/audio_checkpoints.py', 'core/audio_utils.py',
                           'core/loudness.py', 'core/speech_timing.py', 'core/speech_language.py', 'core/dialogue_integrity.py',
                           'core/xtts_text.py', 'core/tts/tts_handler.py', 'core/xtts_compat.py',
                           'core/xtts_worker.py', 'core/providers/tts/xtts_local.py',
                           'core/voice_conditioning.py','core/speech_generation_budget.py'],
            }[stage]
            code = ({'application': self.fingerprint(sys.executable)} if getattr(sys, 'frozen', False)
                    else {name: self.fingerprint(self.project / name) for name in files})
            route = {}
            if stage == 'speech' and not getattr(sys, 'frozen', False):
                from core.stage_checkpoints import stage_code_identity
                code['speech_logic'] = stage_code_identity(self.project, 'speech')
            if stage == 'extract':
                executable = self.project / 'ffmpeg/bin' / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
                route['decoder'] = self.fingerprint(executable)
            elif stage == 'separate':
                inputs = dict(audio=self.fingerprint(inputs['audio_path']))
                route = dict(device=provider.device, runtime=provider.runtime,
                    model=self.fingerprint(Path(provider.models_dir)/'955717e8-8726e21a.th'))
                if getattr(provider, 'runtime_identity', None):
                    route['runtime_identity'] = provider.runtime_identity
            elif stage == 'speech':
                # Other voice engines retain their established execution until
                # their complete model/reference contracts can be fingerprinted.
                from core.providers.tts.xtts_local import XTTSLocalProvider
                if not isinstance(provider, XTTSLocalProvider) or actor != 'CLONED_USER':
                    return None
                model = Path(provider.model_path or self.project / 'models/xtts/default')
                route = dict(runtime=provider.runtime, device=provider.device,
                             model=self.fingerprint(model))
                if provider.runtime == 'cuda':
                    from core.cuda_runtime import validate
                    # A job uses a frozen, already selected runtime. Rehashing
                    # its dependency metadata for every cue/retry can cost
                    # hours. Validate once per job, as for the CPU profile;
                    # code_unchanged above still disables reuse on source edits.
                    with self.lock:
                        if 'cuda-speech-runtime' not in self.fingerprints:
                            self.fingerprints['cuda-speech-runtime'] = validate('speech')['identity']
                        route['runtime_identity'] = self.fingerprints['cuda-speech-runtime']
                elif provider.runtime == 'isolated':
                    from core.xtts_runtime import validate
                    with self.lock:
                        if 'xtts-runtime' not in self.fingerprints:
                            self.fingerprints['xtts-runtime'] = validate()['identity']
                        route['runtime_identity'] = self.fingerprints['xtts-runtime']
            if stage in ('separate', 'speech') and not route.get('runtime_identity'):
                from core.python_runtime import worker_python
                executable = Path(getattr(provider, 'worker_interpreter', None) or worker_python())
                route['interpreter'] = self.fingerprint(executable)
                # Package updates change METADATA or RECORD, including wheel
                # content records, without hashing every weight for each cue.
                runtime = executable.parent
                route['packages'] = self.fingerprint(runtime / 'Lib/site-packages') if (
                    runtime / 'Lib/site-packages').is_dir() else self.fingerprint(runtime)
            return digest(dict(schema='reflow.audio-key.v1', stage=stage,
                source=self.checkpoints.manifest.data['source']['sha256'],
                inputs=inputs, route=route, code=code))
        except RenderCancelled:
            raise
        except (OSError, ValueError, KeyError, TypeError) as error:
            logging.warning('Audio recovery unavailable for %s: %s', stage, error)
            return None

    def folder(self, stage, key):
        if stage not in ('extract', 'separate', 'speech') or len(key) != 64 or any(
                char not in '0123456789abcdef' for char in key):
            raise ValueError('Invalid audio checkpoint')
        return safe_path(self.root / stage / key)

    def load(self, stage, key):
        if key is None or not self.checkpoints.code_unchanged():
            return None
        try:
            check_cancelled()
            folder = self.folder(stage, key)
            descriptor = folder / 'index.json'
            if descriptor.stat().st_size > 16384:
                raise ValueError('Oversized audio checkpoint descriptor')
            data = json.loads(descriptor.read_text(encoding='utf-8'))
            expected_roles = {'extract': {'audio'}, 'separate': {'vocals', 'background'}, 'speech': {'take'}}
            if (not isinstance(data, dict) or not isinstance(data.get('files'), dict)
                    or data.get('key') != key or data.get('stage') != stage
                    or set(data['files']) != expected_roles[stage]):
                raise ValueError('Invalid audio checkpoint descriptor')
            paths = {}
            for role, record in data['files'].items():
                if not isinstance(record, dict):
                    raise ValueError('Invalid audio checkpoint record')
                sha = record['sha256']
                if len(sha) != 64 or any(char not in '0123456789abcdef' for char in sha):
                    raise ValueError('Invalid audio checkpoint checksum')
                path = safe_path(folder / (sha + '.wav'))
                identity = file_identity(path)
                if identity['sha256'] != sha or identity['bytes'] != record['bytes']:
                    raise ValueError('Audio checkpoint checksum mismatch')
                with wave.open(str(path), 'rb') as audio:
                    if audio.getnframes() <= 0 or audio.getcomptype() != 'NONE':
                        raise ValueError('Invalid recovery audio')
                paths[role] = str(path)
            self.checkpoints.event(stage, 'hit', key)
            logging.info('[CHECKPOINT] Reused completed %s audio.', stage)
            return paths
        except FileNotFoundError:
            return None
        except RenderCancelled:
            raise
        except (OSError, ValueError, KeyError, TypeError, wave.Error, EOFError) as error:
            logging.warning('Ignoring damaged %s recovery audio: %s', stage, error)
            return None

    def store(self, stage, key, files):
        if key is None or not self.checkpoints.code_unchanged():
            return
        try:
            folder = self.folder(stage, key)
            folder.mkdir(parents=True, exist_ok=True)
            safe_path(folder)
            records = {}
            for role, source in files.items():
                check_cancelled()
                # A unique pending file prevents two jobs from publishing a
                # partially written WAV or overwriting each other's temporary file.
                fd, pending = tempfile.mkstemp(dir=folder, suffix='.pending')
                os.close(fd)
                try:
                    with open(source, 'rb') as incoming, open(pending, 'wb') as outgoing:
                        while block := incoming.read(1024 * 1024):
                            check_cancelled()
                            outgoing.write(block)
                        outgoing.flush()
                        os.fsync(outgoing.fileno())
                    record = file_identity(pending)
                    with wave.open(pending, 'rb') as audio:
                        if audio.getnframes() <= 0:
                            raise ValueError('Empty recovery audio')
                    destination = safe_path(folder / (record['sha256'] + '.wav'))
                    os.replace(pending, destination)
                    records[role] = dict(sha256=record['sha256'], bytes=record['bytes'])
                finally:
                    Path(pending).unlink(missing_ok=True)
            check_cancelled()
            _publish_bytes(folder / 'index.json', json.dumps(
                dict(key=key, stage=stage, files=records)).encode('utf-8'))
            self.checkpoints.event(stage, 'stored', key)
        except RenderCancelled:
            raise
        except (OSError, ValueError, wave.Error, EOFError) as error:
            logging.warning('Could not save %s recovery audio: %s', stage, error)
