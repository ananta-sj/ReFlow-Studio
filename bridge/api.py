"""The entire JS-callable surface of the Python backend.

Every method on PythonBridge is reachable from the frontend via
`window.pywebview.api.*` - nothing else is. This class IS the security
boundary: there's no HTTP server and no socket, so the only way JS can
reach Python at all is through a method defined here.
"""

import os
import re
import shutil
import threading
import uuid
import math
from functools import wraps
from contextlib import nullcontext
from copy import deepcopy

import webview

import config
from core import marketplace, model_detect, recommended_models, render_state, web_search
from core.credential_store import CredentialError, delete_credential, get_credential, set_credential
from core.downloader import download_with_progress
from core.hardware_monitor import AIRLLM_TRANSLATE_COST, AIRLLM_TRANSLATE_VRAM_MB, HardwareMonitor, _DEVICE_SPEEDUP
from core.hardware_profile import HardwareProfileStore
from core.languages import LANGUAGES
from core.model_registry import ModelRegistry
from core.node_registry import build_default_graph
from core.queue_manager import QueueManager
from core.settings import Settings, WHISPER_MODEL_SIZES
from bridge import push
from core.render_context import RenderContext, bind_job, check_cancelled, RenderCancelled, current_job
from core import deletion_plan
from core.session_state import SessionState

_SEARCH_CREDENTIAL_REF = "reflow.web_search.api_key"


def _graph_change(method):
    @wraps(method)
    def changed(self, *args, **kwargs):
        with getattr(self, '_graph_lock', self._render_lock):
            previous = deepcopy(self.graph)
            result = method(self, *args, **kwargs)
            if result.get('ok') and hasattr(self, '_graph_state'):
                try:
                    self._graph_state.save(self.graph)
                except Exception as exc:
                    self.graph = previous
                    return {'ok': False, 'message': f'Node change could not be saved: {exc}'}
            return result
    return changed


def _graph_read(method):
    @wraps(method)
    def read(self, *args, **kwargs):
        with getattr(self, '_graph_lock', nullcontext()):
            return method(self, *args, **kwargs)
    return read


def _safe_download_filename(source_url, fallback="model.bin"):
    """Extracts a filesystem-safe filename from a user-supplied download
    URL (the Marketplace's "Local Download" URL field accepts any URL, by
    design - see core/recommended_models.py's docstring on "connect to
    any possible model"). The original version only split on "/", so a
    crafted URL ending in a backslash-based traversal sequence (e.g.
    "...\\..\\..\\..\\Users\\Public\\Desktop\\evil.bat") passed straight
    through unsanitized - str.split("/") never touches backslashes, and
    os.path.join() then happily composed a path that escaped the intended
    download directory entirely on Windows. Reproduced and confirmed
    before this fix, not just theorized.

    Splits on BOTH separators regardless of the current OS (this app now
    also targets Linux/macOS, where a lone os.path.basename() call
    wouldn't catch a backslash-based sequence either, since backslash is a
    valid filename character there) and rejects anything that normalizes
    to empty or pure dots."""
    candidate = re.split(r"[\\/]", source_url.split("?")[0].strip())[-1]
    if not candidate or set(candidate) <= {"."}:
        return fallback
    return candidate

# Which registry stage type(s) back each pipeline-execution stage name -
# "tts_rvc" is genuinely two registry stages (a TTS model AND a voice
# model both contribute to that one pipeline step), everything else is 1:1.
_PIPELINE_TO_REGISTRY_STAGES = {
    "stt": ["stt"],
    "translate": ["translation"],
    "tts_rvc": ["tts", "voice"],
    "lipsync": ["lipsync"],
    "enhance": ["enhancer"],
    "content_filter": ["filter"],
    "profanity_filter": ["profanity_filter"],
}
# A local model around this size is what the flat per-stage defaults in
# core/hardware_monitor.py were calibrated against - an actual model
# bigger/smaller than this scales the estimate proportionally instead of
# every model of a given stage type costing the same regardless of size.
_REFERENCE_MODEL_MB = 1024.0

# Maps a pipeline status string to the node id it corresponds to, so the
# node graph can highlight the currently-executing node. Kept here (not
# imported from ui.workers.pipeline_worker) so bridge/ has zero dependency
# on the PyQt6 tree, which is retired once this migration reaches parity.
_STAGE_KEYWORDS = [
    ("SEPARATING", "separate"),
    ("TRANSCRIBING", "stt"),
    ("TRANSLATING", "translate"),
    ("DUBBING", "tts_rvc"),
    ("MIXING", "mix"),
    ("LIP SYNC", "lipsync"),
    ("ENHANCING", "enhance"),
    ("CONTENT FILTER", "content_filter"),
    ("FINAL MERGE", "output"),
]


def status_to_stage_id(status):
    upper = status.upper()
    for keyword, stage_id in _STAGE_KEYWORDS:
        if keyword in upper:
            return stage_id
    return None


def _probe_duration(path):
    import subprocess
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path]
        # Called synchronously from estimate_job()/estimate_job_all_devices()
        # every time the user picks a video or flips a stage toggle - unlike
        # a render (deliberately run on its own thread, see start_render()),
        # this runs on whatever thread pywebview dispatches js_api calls on,
        # so a hang here without a timeout would freeze the whole UI on an
        # everyday action, not just during a render.
        duration = float(subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=15).decode().strip())
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('Media duration is unavailable')
        return duration
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError):
        return 0.0


def _active_stages(params, profanity_filter_active=False):
    stages = ["stt", "translate", "tts_rvc", "mix"]
    if params.get('lang') == 'source':
        stages.remove('translate')
    if params.get("keep_bg"):
        stages.append("separate")
    if params.get("lipsync"):
        stages.append("lipsync")
    if params.get("enhance"):
        stages.append("enhance")
    if params.get("content_filter"):
        stages.append("content_filter")
    # Unlike the flags above, profanity filtering has no RenderParams
    # checkbox - it's opt-in purely by having an active model connected in
    # the Marketplace (same "on iff connected" pattern AirLLM uses for
    # translation), so the caller passes registry state instead of a param.
    if profanity_filter_active:
        stages.append("profanity_filter")
    return stages


def _parallel_speedup_factor(parallel_workers, device_kind):
    """No unmeasured speed discount: CPU/GPU model inference is serialized.
    Preparation/mastering can overlap, but worker count is not a benchmark.
    """
    return 1.0


def _fits_device(approx_vram_gb, profile):
    """Soft "would this model comfortably run on this machine" check for the
    Marketplace's "Best For This Device" hint - compares recommended_models.py's
    approx_vram_gb against core/hardware_profile.py's captured snapshot.
    Deliberately conservative (headroom multipliers below 1.0) since this is
    a hint to steer a first-time pick, not the real ETA/VRAM estimator."""
    if approx_vram_gb is None or profile is None:
        return False
    device = profile.get("best_device") or {}
    if device.get("kind") == "dedicated":
        vram_total_mb = device.get("vram_total_mb")
        if not vram_total_mb:
            return False
        return approx_vram_gb <= (vram_total_mb / 1024) * 0.85
    # Integrated GPU or CPU-only - the practical ceiling is system RAM,
    # shared with the OS and everything else running, hence the much more
    # conservative multiplier than the dedicated-GPU case above.
    ram_total_gb = profile.get("ram_total_gb")
    if not ram_total_gb:
        return False
    return approx_vram_gb <= ram_total_gb * 0.5


class PythonBridge:
    def __init__(self):
        self._persistence_warnings = []
        self._persistence_warning_lock = threading.Lock()
        self.monitor = HardwareMonitor()
        from core.graph_state import GraphState
        self._graph_lock = threading.RLock()
        self._graph_state = GraphState(os.path.join(config.BASE_DIR, 'graph.json'), self._queue_persistence_warning)
        self.graph = self._graph_state.load()
        self.settings = Settings(warning=self._queue_persistence_warning)
        from core.ui_preferences import UIPreferences
        self._ui_preferences = UIPreferences(warning=self._queue_persistence_warning)
        self.registry = ModelRegistry(warning=self._queue_persistence_warning)
        self.hardware_profile = HardwareProfileStore(warning=self._queue_persistence_warning)
        self.queue_manager = QueueManager(os.path.join(config.BASE_DIR, 'queue_state.json'), self._queue_persistence_warning)
        # Set by main.py right after window creation, to a bound method
        # (tray.minimize_to_tray) - never to the TrayController/Window
        # object itself. pywebview auto-generates its JS-callable surface by
        # recursively walking every non-callable attribute reachable from
        # this bridge instance (see webview/util.py's get_functions()); a
        # plain object attribute gets walked into, which for a TrayController
        # holding a live pywebview Window means recursing into its native
        # WinForms/COM proxy (window.native.AccessibilityObject...), which
        # returns a fresh proxy for literally any attribute name and blows
        # the stack - reproduced live. A bound method is directly callable,
        # so pywebview registers it and does not recurse further into it.
        self._minimize_to_tray_fn = None
        self._tray_stop_fn = None
        self._render_thread = None
        self._render_lock = threading.Lock()
        self._render_killed = False
        self._active_job = None
        self._active_downloads = set()
        self._download_contexts = {}
        self._deletion_previews = {}
        self._session = SessionState()
        self._render_busy = False
        self._current_queue_item = None
        self._maximized = False
        self._pre_maximize_rect = None

    # --- settings ---
    def _queue_persistence_warning(self, message):
        with self._persistence_warning_lock:
            self._persistence_warnings.append(message)

    def _flush_persistence_warnings(self):
        lock = getattr(self, '_persistence_warning_lock', None)
        if lock is None or not webview.windows:
            return
        with lock:
            while self._persistence_warnings:
                try:
                    push.emit('log', {'level': 'warning', 'message': self._persistence_warnings[0]})
                except Exception:
                    return  # Keep the warning available for the next read.
                self._persistence_warnings.pop(0)

    def get_settings(self):
        from core.xtts_runtime import readiness
        from core.recognition_runtime import readiness as recognition_readiness
        from core.nllb_runtime import readiness as nllb_readiness
        from core.m2m100_runtime import readiness as m2m100_readiness
        from core.separation_runtime import readiness as separation_readiness
        from core.visual_runtime import readiness as visual_readiness
        result = {"values": self.settings.all(), "whisper_model_sizes": WHISPER_MODEL_SIZES,
                  "xtts_runtime_status": readiness()['status'],
                  "recognition_runtime_status": recognition_readiness()['status'],
                  "nllb_runtime_status": nllb_readiness()['status'],
                  "m2m100_runtime_status": m2m100_readiness()['status'],
                  "separation_runtime_status": separation_readiness()['status'],
                  "enhancement_runtime_status": visual_readiness()['status']}
        self._flush_persistence_warnings()
        return result

    def get_ui_preferences(self):
        result = self._ui_preferences.all()
        self._flush_persistence_warnings()
        return result

    def update_ui_preferences(self, partial):
        return self._ui_preferences.update(partial)

    def list_languages(self):
        """The one source of truth for supported translation target
        languages (core/languages.py) - Dashboard, Settings, and the
        first-run wizard all fetch this instead of each hardcoding their
        own list, which is exactly how 3 separate 6-language copies (one
        of them silently defaulting anything unrecognized to English) had
        drifted out of sync with each other before this existed."""
        return [{"code": code, "name": name} for code, name in LANGUAGES]

    def update_settings(self, partial):
        if isinstance(partial,dict) and partial.get("enhancement_runtime")=="isolated":
            from core.visual_runtime import validate,model_contract
            validate();model_contract()
        if isinstance(partial,dict) and partial.get('separation_runtime')=='isolated':
            from core.separation_runtime import validate,model_contract
            validate();model_contract()
        if isinstance(partial,dict) and partial.get('m2m100_runtime')=='isolated':
            from core.m2m100_runtime import validate,model_contract
            validate();model_contract()
        if isinstance(partial, dict) and partial.get('nllb_runtime') == 'isolated':
            from core.nllb_runtime import validate
            validate()
        if isinstance(partial, dict) and partial.get('recognition_runtime') == 'isolated':
            from core.recognition_runtime import validate
            validate()
        if isinstance(partial, dict) and partial.get('xtts_runtime') == 'isolated':
            from core.xtts_runtime import validate
            validate()  # Reject an unavailable recipe before publishing settings.
        if isinstance(partial, dict) and partial.get('dialogue_text_consent') is True:
            from core.dialogue_connections import fingerprint
            partial = dict(partial)
            values = {**self.settings.all(), **partial}
            partial['dialogue_consent_fingerprint'] = fingerprint(values, self.registry)
        elif isinstance(partial, dict):
            partial = {key: value for key, value in partial.items() if key != 'dialogue_consent_fingerprint'}
        return self.settings.update(partial)

    def get_dialogue_readiness(self):
        from core.dialogue_connections import readiness
        return readiness(self.settings.all(), self.registry)

    def get_engine_readiness(self, params, template_id='video_dub', verify_runtime=False):
        from core.engine_readiness import inspect
        if type(verify_runtime) is not bool:
            raise ValueError('Runtime verification must be explicitly enabled or disabled')
        if verify_runtime:
            with self._render_lock:
                if self._deletion_busy():
                    raise RuntimeError('Wait for the active job, download or runtime check to finish.')
                self._runtime_check_busy = True
        # Match the same template/cast mapping used when a job is accepted.
        try:
            normalized = {**{'lang': 'en', 'voice': 'CLONED_USER'}, **(params or {})}
            arguments = (self.registry.snapshot(), template_id, self._template_kwargs(template_id, normalized))
            return inspect(*arguments, verify_runtime=verify_runtime, xtts_runtime=self.settings.get('xtts_runtime'),
                recognition_runtime=self.settings.get('recognition_runtime'), nllb_runtime=self.settings.get('nllb_runtime'),
                m2m100_runtime=self.settings.get('m2m100_runtime'), separation_runtime=self.settings.get('separation_runtime'), enhancement_runtime=self.settings.get('enhancement_runtime'))
        finally:
            if verify_runtime:
                with self._render_lock:
                    self._runtime_check_busy = False

    def list_source_languages(self):
        from core.source_language import SOURCE_LANGUAGE_NAMES
        return [{"code": code, "name": name} for code, name in SOURCE_LANGUAGE_NAMES.items()]

    def reset_settings(self):
        return self.settings.reset()

    # --- window chrome (frameless window, custom HTML title bar) ---
    def minimize_window(self):
        webview.windows[0].minimize()

    def set_tray_handlers(self, minimize_fn, stop_fn):
        """Called once by main.py right after the tray controller is built.
        Only ever pass bound methods here (e.g. tray.minimize_to_tray),
        never the TrayController or Window object itself - see the
        docstring on self._minimize_to_tray_fn in __init__ for why."""
        self._minimize_to_tray_fn = minimize_fn
        self._tray_stop_fn = stop_fn

    def minimize_to_tray(self):
        """Hides the window entirely (no taskbar entry - see core/tray.py)
        instead of a normal OS minimize, with a tray icon to restore it -
        the render thread already runs independently of window visibility,
        so this is purely a "get it off my screen without losing the job"
        action, the same way WinRAR can be minimized while it keeps zipping."""
        if self._minimize_to_tray_fn:
            self._minimize_to_tray_fn()
        return {"ok": self._minimize_to_tray_fn is not None}

    def toggle_maximize_window(self):
        """Snap to the monitor's *working area* (excludes the taskbar), not
        window.maximize(). On Windows, WinForms' native Maximized state for a
        BORDERLESS form (required for the custom title bar) covers the whole
        monitor including the taskbar - a well-known WinForms quirk, not a
        pywebview bug - since borderless forms don't get the OS's normal
        "maximize to work area" negotiation without handling WM_GETMINMAXINFO
        directly.

        Goes through raw Win32 calls (GetWindowRect/SetWindowPos/
        SystemParametersInfoW) instead of pywebview's window.resize()/move(),
        which apply their own logical-to-physical DPI scaling on top of
        values that may already be physical - that mismatch is what produced
        a window bigger than the screen itself in an earlier version of this
        function. GetWindowRect and SystemParametersInfoW(SPI_GETWORKAREA)
        both operate in the same raw pixel space, so there's no scaling to
        get wrong.
        """
        import sys

        if sys.platform != "win32":
            # Mac/Linux window managers already respect the dock/taskbar for
            # borderless windows, so the native call is fine there.
            window = webview.windows[0]
            window.restore() if self._maximized else window.maximize()
            self._maximized = not self._maximized
            return

        import ctypes

        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        SWP_NOZORDER = 0x0004
        SWP_SHOWWINDOW = 0x0040
        SPI_GETWORKAREA = 0x0030

        hwnd = user32.FindWindowW(None, webview.windows[0].title)
        if not hwnd:
            return

        if self._maximized:
            if self._pre_maximize_rect:
                left, top, right, bottom = self._pre_maximize_rect
                user32.SetWindowPos(
                    hwnd, None, left, top, right - left, bottom - top,
                    SWP_NOZORDER | SWP_SHOWWINDOW,
                )
            self._maximized = False
            return

        current = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(current))
        self._pre_maximize_rect = (current.left, current.top, current.right, current.bottom)

        work_area = RECT()
        user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work_area), 0)
        user32.SetWindowPos(
            hwnd, None,
            work_area.left, work_area.top,
            work_area.right - work_area.left, work_area.bottom - work_area.top,
            SWP_NOZORDER | SWP_SHOWWINDOW,
        )
        self._maximized = True

    def close_window(self):
        if self._tray_stop_fn:
            self._tray_stop_fn()
        webview.windows[0].destroy()

    # --- hardware / devices ---
    def get_hardware_snapshot(self, device_id=None):
        device_id = device_id or self.monitor.default_device_id()
        sample = self.monitor.sample(device_id)
        device = next((d for d in self.monitor.devices if d.id == device_id), None)
        return {
            "cpu_name": self.monitor.cpu_name,
            "cpu_percent": sample["cpu_percent"],
            "ram_used_gb": round(sample["ram_used_gb"], 1),
            "ram_total_gb": round(sample["ram_total_gb"], 1),
            "vram_used_mb": sample["vram_used_mb"],
            "vram_total_mb": sample["vram_total_mb"],
            "gpu_name": device.name if device else "Unknown",
            "gpu_kind": device.kind if device else "cpu",
            "default_device_id": self.monitor.default_device_id(),
            "devices": [
                {"id": d.id, "label": d.label(), "kind": d.kind, "backend": d.backend}
                for d in self.monitor.devices
            ],
        }

    def _model_resource_override(self, entry, base_cost, base_vram_mb):
        """(cost_ratio, vram_mb) to use INSTEAD of a pipeline stage's flat
        default, based on the model actually active for it - or None to
        keep using the flat default (nothing more specific to go on)."""
        if entry is None:
            return None
        if entry.get("request_preset") == "airllm":
            return (AIRLLM_TRANSLATE_COST, AIRLLM_TRANSLATE_VRAM_MB)
        if entry["kind"] in ("cloud_api", "local_api"):
            # Remote work consumes no local VRAM. Keep the baseline duration
            # until measurements establish the service's latency.
            return (base_cost, 0)  # Remote latency is unknown; do not invent a speedup.
        size_bytes = (entry.get("meta") or {}).get("file_size_bytes")
        if (type(size_bytes) not in (int, float) or not math.isfinite(size_bytes)
                or size_bytes <= 0):
            return None  # not downloaded yet / size unknown - flat default stands
        size_mb = size_bytes / (1024 * 1024)
        scale = max(0.2, min(5.0, size_mb / _REFERENCE_MODEL_MB))
        return (base_cost * scale, size_mb * 1.3)  # loaded-in-memory overhead vs on-disk size

    def _estimate_overrides(self, device_kind="cpu", parallel_workers=1, cast=None):
        """Per-pipeline-stage (cost_ratio, vram_mb) overrides built from
        whichever model is actually active for each stage right now - see
        _model_resource_override(). A stage with no override falls back to
        core/hardware_monitor.py's flat default, so this never breaks
        estimates for stages nobody's touched in the Marketplace.
        Speech sizing here is combined for compatibility; the final resource
        report splits speech components by their actual execution processors.
        Worker count is not a measured inference-throughput discount."""
        active = self.registry.get_active_map()
        cost_overrides = {}
        vram_overrides = {}
        for pipeline_stage, registry_types in _PIPELINE_TO_REGISTRY_STAGES.items():
            base_cost = self.monitor.base_stage_cost(pipeline_stage) / len(registry_types)
            base_vram = self.monitor.base_stage_vram_mb(pipeline_stage) / len(registry_types)
            total_cost = 0.0
            total_vram = 0.0
            for rt in registry_types:
                result = self._model_resource_override(active.get(rt), base_cost, base_vram)
                total_cost += result[0] if result else base_cost
                total_vram += result[1] if result else base_vram
            cost_overrides[pipeline_stage] = total_cost
            vram_overrides[pipeline_stage] = total_vram

        if cast:
            from core.providers.resolve import voice_entry
            entries = [voice_entry(self.registry, actor) if actor != 'CLONED_USER' else None for actor in cast]
            base_cost = self.monitor.base_stage_cost('tts_rvc') / 2
            base_vram = self.monitor.base_stage_vram_mb('tts_rvc') / 2
            voice_costs, voice_memory = [], {}
            needs_tts = False
            for actor, entry in zip(cast, entries):
                is_f5 = entry and entry.get('kind') == 'local_file' and entry.get('request_preset') == 'f5tts'
                needs_tts |= not is_f5
                if actor == 'CLONED_USER':
                    voice_costs.append(0)
                    continue
                override = self._model_resource_override(entry, base_cost, base_vram)
                voice_costs.append(override[0] if override else base_cost)
                voice_memory[entry['id'] if entry else actor] = override[1] if override else base_vram
            tts = self._model_resource_override(active.get('tts'), base_cost, base_vram) if needs_tts else (0, 0)
            cost_overrides['tts_rvc'] = (tts[0] if tts else base_cost) + max(voice_costs, default=0)
            # Actors can retain separate loaded providers; count each unique
            # checkpoint once rather than the unrelated active Voice entry.
            vram_overrides['tts_rvc'] = (tts[1] if tts else base_vram) + sum(voice_memory.values())

        indic = active.get('tts') and active['tts'].get('request_preset') == 'indicf5'
        if not (indic and (not cast or 'CLONED_USER' in cast)):
            cost_overrides["tts_rvc"] *= _parallel_speedup_factor(parallel_workers, device_kind)
        return cost_overrides, vram_overrides

    def _estimate_routes(self, device_id, stage_flags):
        # These stages are CPU-bound or served externally regardless of the
        # chosen GPU. Their duration must not receive the GPU speed factor.
        routes = {'stt': 'cpu', 'translate': 'cpu', 'mix': 'cpu', 'profanity_filter': 'cpu'}
        recognition = self.registry.get_active('stt')
        if recognition and recognition.get('request_preset') == 'whisper_turbo':
            routes['stt'] = 'cuda:0'
        translation = self.registry.get_active('translation')
        if translation and translation.get('request_preset') == 'indictrans2':
            routes['translate'] = 'cuda:0'
        for stage, registry_type in (('lipsync', 'lipsync'), ('enhance', 'enhancer'),
                                     ('content_filter', 'filter')):
            entry = self.registry.get_active(registry_type)
            if entry and entry.get('kind') in ('cloud_api', 'local_api'):
                routes[stage] = 'cpu'  # Local GPU selection cannot speed up a service.
        active_filter = self.registry.get_active('filter')
        if not active_filter or active_filter.get('request_preset') != 'image_classifier':
            routes['content_filter'] = 'cpu'
        from core.optional_runtime import interpreter
        active_lipsync = self.registry.get_active('lipsync')
        if active_lipsync and (active_lipsync.get('meta') or {}).get('adapter') == 'musetalk' and interpreter('musetalk'):
            routes['lipsync'] = 'cpu'
        cast = stage_flags.get('cast_list') or [stage_flags.get('voice', 'CLONED_USER')]
        from core.speech_language import actor_uses_f5
        from core.providers.resolve import voice_entry
        selected_voices = [voice_entry(self.registry, actor) for actor in cast if actor != 'CLONED_USER']
        tts = self.registry.get_active('tts')
        if (tts and tts.get('kind') in ('cloud_api', 'local_api') and
                all(entry and entry.get('kind') in ('cloud_api', 'local_api') for entry in selected_voices)):
            routes['tts_rvc'] = 'cpu'
        if cast and all(actor_uses_f5(self.registry, actor) for actor in cast) and interpreter('f5'):
            routes['tts_rvc'] = 'cpu'
        return routes

    def _speech_resource_components(self, device_id, cast):
        """Resolve the same base speech/voice processor choices as execution."""
        from core.optional_runtime import interpreter
        from core.providers.resolve import voice_entry
        from core.speech_language import actor_uses_f5
        base_cost = self.monitor.base_stage_cost('tts_rvc') / 2
        base_memory = self.monitor.base_stage_vram_mb('tts_rvc') / 2
        def normalized(device):
            return 'cpu' if device.startswith('other:') else 'cuda:0' if device == 'cuda' else device
        workspace = normalized(device_id)
        components = []
        seen = set()
        needs_tts = False
        for actor in cast:
            is_f5 = actor_uses_f5(self.registry, actor)
            needs_tts |= not is_f5
            if actor == 'CLONED_USER':
                continue
            entry = voice_entry(self.registry, actor)
            identifier = entry['id'] if entry else actor
            if identifier in seen:
                continue
            seen.add(identifier)
            external = bool(entry and entry.get('kind') in ('cloud_api', 'local_api'))
            device = 'cpu' if external or (is_f5 and interpreter('f5')) else workspace
            cost, memory = self._model_resource_override(entry, base_cost, base_memory) or (base_cost, base_memory)
            components.append(dict(role='voice', id=identifier, device=device, cost_ratio=cost, model_memory_mb=memory))
        if needs_tts:
            entry = self.registry.get_active('tts')
            device = workspace
            if entry and entry.get('kind') in ('cloud_api', 'local_api'):
                device = 'cpu'
            elif entry and entry.get('request_preset') == 'indicf5':
                device = normalized((entry.get('meta') or {}).get('speech_device') or workspace)
            cost, memory = self._model_resource_override(entry, base_cost, base_memory) or (base_cost, base_memory)
            components.insert(0, dict(role='tts', id=entry.get('id', 'selected-tts') if entry else 'default', device=device,
                                     cost_ratio=cost, model_memory_mb=memory))
        return components

    def _resource_estimate(self, duration, stages, device_id, stage_flags):
        from core.parallel_policy import segment_buffer_window
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
            raise ValueError('Source duration must be finite and nonnegative')
        device_id = 'cpu' if device_id.startswith('other:') else 'cuda:0' if device_id == 'cuda' else device_id
        workers = stage_flags.get('parallel_workers', 1)
        buffer_window = segment_buffer_window(workers)
        cast = stage_flags.get('cast_list') or [stage_flags.get('voice', 'CLONED_USER')]
        cost, memory = self._estimate_overrides(self.monitor.device_kind(device_id), workers, cast)
        routes = self._estimate_routes(device_id, stage_flags)
        speech = self.registry.get_active('tts')
        components = self._speech_resource_components(device_id, cast) if 'tts_rvc' in stages else []
        speech_devices = {component['device'] for component in components}
        indic = bool(speech and speech.get('request_preset') == 'indicf5' and
                     any(component['role'] == 'tts' for component in components))
        if components:
            # Compute device factors per component before the combined stage.
            # A CPU base TTS must not receive its RVC actor's GPU discount.
            weighted = [(component, component['cost_ratio'] * _DEVICE_SPEEDUP.get(
                self.monitor.device_kind(component['device']), 1.0)) for component in components]
            cost['tts_rvc'] = sum(value for component, value in weighted if component['role']=='tts') + max(
                (value for component, value in weighted if component['role']=='voice'), default=0)
            routes['tts_rvc'] = 'cpu'  # Device factors are already included above.
        eta = self.monitor.estimate_eta_seconds(duration, stages, device_id,
            stage_cost_overrides=cost, stage_device_overrides=routes)
        # CPU audio buffers increase RAM, not dedicated GPU memory. This is
        # a planning approximation for several full-length decoded PCM tracks.
        media = any(stage in stages for stage in ('stt', 'separate', 'tts_rvc', 'mix'))
        pcm_mb = duration * 48000 * 4 * 5 / (1024 * 1024) if media else 0
        worker_buffers_mb = buffer_window * 9 * 48000 * 4 / (1024 * 1024) if components else 0
        budgets = {}
        unknown_memory = []
        for stage in stages:
            allocations = components if stage == 'tts_rvc' else [dict(device=routes.get(stage, device_id),
                model_memory_mb=memory.get(stage, self.monitor.base_stage_vram_mb(stage)))]
            for allocation in allocations:
                device = allocation['device']
                if device != 'cpu':
                    value = allocation['model_memory_mb']
                    if not value:
                        budgets[device] = None
                        unknown_memory.append(stage)
                    elif budgets.get(device, 0) is not None:
                        budgets[device] = budgets.get(device, 0) + value
        from core.speech_language import actor_uses_f5
        warnings = []
        if unknown_memory:
            warnings.append('GPU memory is unknown for ' + ', '.join(sorted(set(unknown_memory))) + '. A complete memory budget cannot be calculated.')
        recognition = self.registry.get_active('stt')
        if 'stt' in stages and recognition and recognition.get('request_preset') == 'whisper_turbo':
            warnings.append('Whisper turbo recognition uses the first NVIDIA GPU and releases it before translation. Startup, recognition speed and memory are uncalibrated estimates.')
        translation = self.registry.get_active('translation')
        if 'translate' in stages and translation and translation.get('request_preset') == 'indictrans2':
            warnings.append('IndicTrans2 translation uses the first NVIDIA GPU even when the workspace uses CPU. Startup, translation speed and GPU memory are uncalibrated estimates; the worker is released before Hindi speech.')
        if indic:
            warnings.append('Hindi speech uses its separately selected processor. IndicF5 startup, pace and memory are not calibrated in this estimate; speech calls share one worker and do not gain the generic parallel speedup.')
        if components and any(actor_uses_f5(self.registry, actor) for actor in cast):
            warnings.append('F5 timing is not calibrated. CPU speech generation can take several minutes per short cue; reference transcription adds more time.')
        if len(speech_devices) > 1:
            warnings.append('Speech generation and voice conversion use different processors; their memory budgets are listed separately.')
        if components:
            warnings.append('Audio buffer estimates assume 9-second clips. Longer clips need more RAM; model memory is additional.')
        reported_routes = {stage: routes.get(stage, device_id) for stage in stages}
        if components:
            reported_routes['tts_rvc'] = next(iter(speech_devices)) if len(speech_devices)==1 else 'mixed'
        return {'eta_seconds': eta,
                'peak_vram_mb': (None if any(value is None for value in budgets.values()) else max(budgets.values(), default=0) or None),
                'peak_vram_by_device_mb': budgets,
                'audio_buffer_ram_mb': round(pcm_mb + worker_buffers_mb, 1),
                'segment_buffer_window': buffer_window if components else 0,
                'speech_components': components,
                'estimate_basis': 'uncalibrated cumulative GPU budget and timing heuristic; excludes downloads and service latency',
                'warnings': warnings,
                'stage_devices': reported_routes}

    def estimate_job(self, video_path, stage_flags, device_id):
        stage_flags = self._estimate_selection(stage_flags)
        duration = _probe_duration(video_path)
        stages = _active_stages(stage_flags, profanity_filter_active=self.registry.get_active("profanity_filter") is not None)
        return self._resource_estimate(duration, stages, device_id, stage_flags)

    def estimate_job_all_devices(self, video_path, stage_flags):
        """Same estimate as estimate_job(), but for every detected device at
        once - probes the video's duration only once (not once per device)
        so a comparison view (GPU vs GPU vs CPU) is cheap to refresh live as
        the user changes toggles."""
        stage_flags = self._estimate_selection(stage_flags)
        duration = _probe_duration(video_path)
        stages = _active_stages(stage_flags, profanity_filter_active=self.registry.get_active("profanity_filter") is not None)
        result = {}
        for d in self.monitor.devices:
            result[d.id] = self._resource_estimate(duration, stages, d.id, stage_flags)
        return result

    @_graph_read
    def _estimate_selection(self, flags):
        flags = deepcopy(flags)
        # Match job acceptance: graph actors own multi-cast; Dashboard owns
        # singleton selection. A caller's stale cast list cannot override it.
        flags['cast_list'] = self._resolve_cast_list({'voice': flags.get('voice', 'CLONED_USER')})
        return flags

    # --- model marketplace ---
    # Replaces the old RVC-only list_voice_models/import_voice_model pair:
    # "voice" is now one of six pluggable stage types, each backed by the
    # same registry (core/model_registry.py) instead of a bespoke list.
    def list_models(self, stage_type=None):
        result = self.registry.list(stage_type)
        for entry in result:
            job = getattr(self, '_download_contexts', {}).get(entry['id'])
            if job and job.cancelled.is_set():
                entry['meta'] = {**(entry.get('meta') or {}), 'cancel_requested': True}
        self._flush_persistence_warnings()
        return result

    def get_active_models(self):
        return self.registry.get_active_map()

    def list_hindi_voices(self):
        from core.indicf5_profiles import available
        return available()

    def whisper_turbo_status(self):
        try:
            from core.whisper_turbo_assets import installed_path, validate_assets, isolated_interpreter
            validate_assets(installed_path())
            isolated_interpreter()
            return {'ready':True,'message':'Installed stronger Whisper recognizer. NVIDIA GPU required.'}
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            return {'ready':False,'message':str(exc)}

    def connect_whisper_turbo(self):
        with self._render_lock:
            try:
                if self._deletion_busy():
                    raise ValueError('Wait for rendering or downloads before changing recognition connections.')
                from core.whisper_turbo_assets import installed_path, validate_assets, isolated_interpreter
                path = installed_path()
                contract = validate_assets(path)
                isolated_interpreter()
                existing = next((entry for entry in self.registry.list('stt')
                    if entry.get('request_preset') == 'whisper_turbo'),None)
                meta = {'recognition_device':'cuda:0','model_revision':contract['revision'],
                        'file_size_bytes':(path/'model.safetensors').stat().st_size}
                if existing:
                    entry = self.registry.update(existing['id'],local_path=str(path),meta=meta,status='installed')
                else:
                    entry = self.registry.add('stt','local_file','Whisper — stronger recognition',
                        local_path=str(path),request_preset='whisper_turbo',status='installed',meta=meta)
                return {'ok':True,'model':entry}
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                return {'ok':False,'message':str(exc)}

    def indictrans2_status(self):
        try:
            from core.indictrans2_assets import installed_path, validate_assets, isolated_interpreter
            validate_assets(installed_path())
            isolated_interpreter()
            return {'ready': True, 'message': 'Installed English-to-Hindi translation. NVIDIA GPU required.'}
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            return {'ready': False, 'message': str(exc)}

    def connect_indictrans2(self):
        with self._render_lock:
            try:
                if self._deletion_busy():
                    raise ValueError('Wait for rendering or downloads before changing translation connections.')
                from core.indictrans2_assets import installed_path, validate_assets, isolated_interpreter
                path = installed_path()
                contract = validate_assets(path)
                isolated_interpreter()
                existing = next((entry for entry in self.registry.list('translation')
                    if entry.get('request_preset') == 'indictrans2'), None)
                meta = {'supported_source_languages':['en'], 'supported_languages':['hi'],
                        'translation_device':'cuda:0', 'model_revision':contract['revision'],
                        'file_size_bytes':(path / 'model.safetensors').stat().st_size}
                if existing:
                    entry = self.registry.update(existing['id'], local_path=str(path), meta=meta, status='installed')
                else:
                    entry = self.registry.add('translation', 'local_file', 'IndicTrans2 — English to Hindi',
                        local_path=str(path), request_preset='indictrans2', status='installed', meta=meta)
                return {'ok':True, 'model':entry}
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                return {'ok':False, 'message':str(exc)}

    def preview_hindi_voice(self, identifier):
        try:
            from core.indicf5_profiles import preview
            return {'ok': True, 'audio': preview(identifier)}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return {'ok': False, 'message': str(exc)}

    def connect_hindi_voice(self, identifier, device, confirmed=False):
        with self._render_lock:
            try:
                if confirmed is not True:
                    raise ValueError('Listen to the reference and confirm its words before connecting.')
                if self._deletion_busy():
                    raise ValueError('Wait for current rendering or downloads before changing the voice.')
                from core.indicf5_profiles import profile, model_path
                from core.providers.tts.indicf5_local import isolated_interpreter
                if device not in ('cpu', 'cuda:0'):
                    raise ValueError('Choose CPU or the first NVIDIA GPU for Hindi speech.')
                item = profile(identifier)
                path = model_path()
                isolated_interpreter(device)
                existing = next((entry for entry in self.registry.list('tts')
                    if entry.get('request_preset') == 'indicf5' and
                    (entry.get('meta') or {}).get('reference_profile') == item['profile_path']), None)
                meta = {**((existing or {}).get('meta') or {}), 'reference_profile': item['profile_path'],
                    'speech_device': device, 'supported_languages': ['hi']}
                if existing:
                    entry = self.registry.update(existing['id'], local_path=path, meta=meta, status='installed')
                else:
                    entry = self.registry.add('tts', 'local_file', 'Hindi — '+identifier.replace('_', ' ').title(),
                        local_path=path, request_preset='indicf5', status='installed', meta=meta)
                return {'ok': True, 'model': entry}
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                return {'ok': False, 'message': str(exc)}

    def capture_hardware_profile(self):
        """Detects and saves this machine's hardware snapshot (see
        core/hardware_profile.py) - called once by the frontend on first
        boot (App.tsx), but a no-op on every later call since capture()
        skips re-detecting once a profile already exists. Powers the
        Marketplace's "Best For This Device" hint on recommended models."""
        result = self.hardware_profile.capture(self.monitor)
        self._flush_persistence_warnings()
        return result

    def list_recommended_models(self, stage_type=None):
        """Curated suggestions (core/recommended_models.py) for the
        Marketplace's "Recommended" section - distinct from find_best_model's
        live HF download-count ranking. Never installed/connected on its
        own; the frontend uses each entry to prefill the existing Add Model
        flow (add_local_model for kind="local_file", the cloud dialog for
        kind="cloud_api") so the user still confirms and, for cloud_api,
        still supplies their own API key.

        Each entry is annotated with best_for_device: True when its
        approx_vram_gb (see recommended_models.py) comfortably fits the
        machine's captured hardware profile - opportunistically captured
        here if App.tsx's boot-time call hasn't happened yet, so this hint
        works even then rather than silently omitting it."""
        profile = self.hardware_profile.get() or self.hardware_profile.capture(self.monitor)

        def annotate(entry):
            return {**entry, "best_for_device": entry.get('kind') == 'local_file' and _fits_device(entry.get("approx_vram_gb"), profile)}

        if stage_type:
            return [annotate(m) for m in recommended_models.RECOMMENDED_MODELS.get(stage_type, [])]
        return {
            stage: [annotate(m) for m in models]
            for stage, models in recommended_models.RECOMMENDED_MODELS.items()
        }

    def set_active_model(self, stage_type, model_id):
        with self._render_lock:
            return self._set_active_model_idle(stage_type, model_id)

    def _set_active_model_idle(self, stage_type, model_id):
        try:
            if model_id:
                entry = self.registry.get(model_id)
                if entry and entry.get('kind') == 'local_file' and entry.get('request_preset') != 'airllm':
                    from core.model_contract import local_contract
                    contract = local_contract(stage_type, entry.get('local_path'), entry.get('request_preset'))
                    if contract['adapter'] == 'indicf5':
                        from core.providers.tts.indicf5_local import load_reference_profile, isolated_interpreter
                        meta = entry.get('meta') or {}
                        load_reference_profile(meta.get('reference_profile'))
                        isolated_interpreter(meta.get('speech_device') or 'cpu')
                    elif contract['adapter'] == 'indictrans2':
                        from core.indictrans2_assets import isolated_interpreter
                        isolated_interpreter()
                    elif contract['adapter'] == 'whisper_turbo':
                        from core.whisper_turbo_assets import isolated_interpreter
                        isolated_interpreter()
            self.registry.set_active(stage_type, model_id)
            return {"ok": True}
        except (ValueError, OSError, RuntimeError, KeyError, TypeError) as e:
            return {"ok": False, "message": str(e)}

    def set_model_instructions(self, model_id, custom_instructions):
        with self._render_lock:
            return self._set_model_instructions_idle(model_id, custom_instructions)

    def _set_model_instructions_idle(self, model_id, custom_instructions):
        """Free-text steering for a connected model - only actually read by
        the translation and profanity_filter providers (see
        core/providers/translation/*.py and
        core/providers/profanity_filter/*.py), since those are the only
        stages backed by an instructable model. Editable anytime, not just
        at add-time, since instructions are the kind of thing you iterate
        on after seeing a render's output."""
        try:
            entry = self.registry.update(model_id, custom_instructions=custom_instructions or "")
            return {"ok": entry is not None, "model": entry}
        except (ValueError, OSError) as error:
            return {"ok": False, "message": str(error)}

    def _deletion_busy(self):
        return (getattr(self, '_runtime_check_busy', False) or getattr(self, "_active_job", None) or
                (self._render_thread and self._render_thread.is_alive()) or
                getattr(self, "_active_downloads", set()))

    def _make_deletion_plan(self, operation, model_id=None):
        if operation == "reset":
            return deletion_plan.reset_plan(config.BASE_DIR, config.TEMP_PATH,
                                            config.OUTPUT_PATH, config.MODELS_DIR)
        entry = self.registry.get(model_id)
        if not entry:
            raise ValueError("Model connection no longer exists.")
        return deletion_plan.model_plan(config.BASE_DIR, config.MODELS_DIR, entry, self.registry.list())

    def _preview_deletion(self, operation, model_id=None):
        with self._render_lock:
            if self._deletion_busy():
                return {"ok": False, "message": "Wait for renders and model downloads/installations to finish."}
            try:
                plan = self._make_deletion_plan(operation, model_id)
                token = uuid.uuid4().hex
                # One outstanding preview prevents unbounded accumulation.
                self._deletion_previews = {token: (operation, model_id, deletion_plan.fingerprint(plan))}
                return deletion_plan.public_preview(plan, token)
            except (ValueError, OSError) as exc:
                return {"ok": False, "message": str(exc)}

    def preview_model_removal(self, model_id):
        return self._preview_deletion("model", model_id)

    def preview_factory_reset(self):
        return self._preview_deletion("reset")

    def _execute_deletion(self, operation, token, model_id=None):
        # Caller holds the lifecycle lock through deletion and finalization.
        if self._deletion_busy():
            return {"ok": False, "message": "Wait for renders and model downloads/installations to finish."}
        saved = getattr(self, "_deletion_previews", {}).pop(token, None)
        if not saved or saved[:2] != (operation, model_id):
            return {"ok": False, "message": "Preview required. Review the affected files again."}
        try:
            plan = self._make_deletion_plan(operation, model_id)
            if deletion_plan.fingerprint(plan) != saved[2]:
                return {"ok": False, "message": "Files or model connections changed. Review a new preview."}
            return deletion_plan.execute(plan, config.BASE_DIR)
        except (ValueError, OSError) as exc:
            return {"ok": False, "message": str(exc)}

    def remove_model(self, model_id, preview_token=None):
        with self._render_lock:
            result = self._execute_deletion("model", preview_token, model_id)
            if not result["ok"]:
                return result
            entry = self.registry.get(model_id)
            try:
                credential = entry.get("credential_ref")
                if credential and not any(e['id'] != model_id and e.get('credential_ref') == credential
                                          for e in self.registry.list()):
                    delete_credential(credential, strict=True)
                self.registry.remove(model_id)
            except Exception as exc:
                return {**result, "ok": False, "message": f"Files processed, but connection finalization failed: {exc}"}
            return result

    def detect_model_type(self, link, link_kind="url"):
        """Best-effort stage_type guess for the Marketplace's "just paste
        a link" flow (see core/model_detect.py) - link_kind is "url" for a
        local-download source URL, or "api_base_url" for a cloud/local-API
        base URL. Always a suggestion for the UI to confirm, never applied
        automatically."""
        if link_kind == "api_base_url":
            return model_detect.detect_from_api_base_url(link)
        return model_detect.detect_from_url(link)

    def get_search_config(self):
        provider = self.settings.get("search_provider")
        engine_id = self.settings.get("search_engine_id")
        configured = web_search.is_configured(provider, get_credential(_SEARCH_CREDENTIAL_REF), engine_id)
        return {"provider": provider, "engine_id": engine_id, "configured": configured}

    def set_search_credentials(self, provider, api_key, engine_id=""):
        try:
            if api_key:
                set_credential(_SEARCH_CREDENTIAL_REF, api_key)
            self.settings.update({"search_provider": provider, "search_engine_id": engine_id})
            return {"ok": True}
        except CredentialError as e:
            return {"ok": False, "message": str(e)}

    def find_best_model(self, stage_type):
        """"Auto" pick for a stage: ranks Hugging Face models by real
        download counts (always available, no config needed), plus an
        opportunistic web-search enrichment if the user has configured a
        search provider in Settings - see core/model_detect.py and
        core/web_search.py. Web results are candidates to review, never
        auto-installed."""
        hf_picks = model_detect.find_best_hf_model(stage_type)

        web_results = []
        provider = self.settings.get("search_provider")
        engine_id = self.settings.get("search_engine_id")
        api_key = get_credential(_SEARCH_CREDENTIAL_REF)
        if web_search.is_configured(provider, api_key, engine_id):
            try:
                web_results = web_search.search(f"best {stage_type} model download", provider, api_key, engine_id)
            except RuntimeError:
                pass  # opportunistic enrichment - the HF pick alone is still useful

        return {"hf_picks": hf_picks, "web_results": web_results}

    def add_cloud_model(self, stage_type, display_name, api_base_url, api_key, request_preset, request_config=None):
        with self._render_lock:
            return self._add_cloud_model_idle(stage_type, display_name, api_base_url, api_key, request_preset, request_config)

    def _add_cloud_model_idle(self, stage_type, display_name, api_base_url, api_key, request_preset, request_config=None):
        """API key goes straight to the OS credential store and is never
        echoed back to JS - only a reference name is persisted in
        models.json."""
        from core.model_contract import cloud_contract
        try:
            meta = cloud_contract(stage_type, api_base_url, request_preset, request_config)
        except ValueError as exc:
            return {'ok': False, 'message': str(exc)}
        credential_ref = f"reflow.{stage_type}.{uuid.uuid4().hex[:8]}"
        try:
            set_credential(credential_ref, api_key)
        except CredentialError as e:
            return {"ok": False, "message": str(e)}
        try:
            entry = self.registry.add(
                stage_type, "cloud_api", display_name,
                api_base_url=api_base_url, credential_ref=credential_ref,
                request_preset=request_preset, status="installed", meta=meta,
            )
        except Exception as exc:
            delete_credential(credential_ref)
            return {'ok': False, 'message': str(exc)}
        push.emit("model_installed", {"modelId": entry["id"], "stageType": stage_type})
        return {"ok": True, "model": entry}

    def add_local_api_model(self, stage_type, display_name, api_base_url, request_preset="custom", request_config=None):
        with self._render_lock:
            return self._add_local_api_model_idle(stage_type, display_name, api_base_url, request_preset, request_config)

    def _add_local_api_model_idle(self, stage_type, display_name, api_base_url, request_preset="custom", request_config=None):
        from core.model_contract import cloud_contract
        try:
            meta = cloud_contract(stage_type, api_base_url, request_preset, request_config)
        except ValueError as exc:
            return {'ok': False, 'message': str(exc)}
        entry = self.registry.add(
            stage_type, "local_api", display_name,
            api_base_url=api_base_url, request_preset=request_preset, status="installed", meta=meta,
        )
        push.emit("model_installed", {"modelId": entry["id"], "stageType": stage_type})
        return {"ok": True, "model": entry}

    def add_airllm_model(self, display_name, hf_model_id, compression=""):
        with self._render_lock:
            return self._add_airllm_model_idle(display_name, hf_model_id, compression)

    def _add_airllm_model_idle(self, display_name, hf_model_id, compression=""):
        """AirLLM (translation stage only) - runs a full HF model with
        layer-by-layer disk offloading instead of an API call or a
        downloaded file, so it doesn't fit local_file/local_api/cloud_api
        cleanly. Stored as a plain registry entry (source_url holds the HF
        model id) marked by request_preset="airllm", which is what
        core/providers/resolve.py's resolve_translation() checks for -
        never used unless the user adds one here AND sets it active."""
        entry = self.registry.add(
            "translation", "local_file", display_name,
            source_url=hf_model_id, request_preset="airllm",
            meta={"compression": compression or None}, status="installed",
        )
        push.emit("model_installed", {"modelId": entry["id"], "stageType": "translation"})
        return {"ok": True, "model": entry}

    def add_local_model(self, stage_type, source_url, display_name, request_preset=None):
        with self._render_lock:
            return self._add_local_model_idle(stage_type, source_url, display_name, request_preset)

    def _add_local_model_idle(self, stage_type, source_url, display_name, request_preset=None):
        """Downloads in a background thread, pushing live progress via the
        same push.emit() channel render progress already uses - see
        core/downloader.py for the speed/ETA metrics themselves.

        request_preset marks which local_file resolution a given stage's
        resolve_*() should use for a downloaded repo (e.g. "image_classifier"
        for the Filter stage - see core/providers/resolve.py) - optional
        since most stages only ever have one local_file shape today."""
        match = next((item for item in recommended_models.RECOMMENDED_MODELS.get(stage_type, [])
                      if item.get('source_url', '').rstrip('/') == source_url.rstrip('/')), None)
        if match and match['kind'] == 'reference':
            return {'ok': False, 'message': 'This project is listed as a reference. Its download has no compatible one-click adapter.'}
        if match and not request_preset:
            request_preset = match.get('request_preset')
        entry = self.registry.add(
            stage_type, "local_file", display_name,
            source_url=source_url, status="downloading", request_preset=request_preset,
        )
        if not hasattr(self, '_active_downloads'):
            self._active_downloads = set()
        self._active_downloads.add(entry['id'])
        try:
            if not hasattr(self, '_download_contexts'):
                self._download_contexts = {}
            self._download_contexts[entry['id']] = RenderContext(config.TEMP_PATH)
            thread = threading.Thread(
                target=self._download_tracked, args=(entry["id"], stage_type, source_url), daemon=True
            )
            thread.start()
        except Exception as exc:
            self._active_downloads.discard(entry['id'])
            job = getattr(self, '_download_contexts', {}).pop(entry['id'], None)
            if job:
                job.cleanup()
            try:
                entry = self.registry.update(entry['id'], status='error')
            except (ValueError, OSError) as save_error:
                return {'ok': False, 'message': f'{exc}; could not save model error status: {save_error}', 'model': entry}
            return {'ok': False, 'message': str(exc), 'model': entry}
        return {"ok": True, "model": entry}

    def _download_tracked(self, model_id, stage_type, source_url):
        try:
            with bind_job(getattr(self, '_download_contexts', {}).get(model_id)):
                self._run_local_download(model_id, stage_type, source_url)
        finally:
            with self._render_lock:
                self._active_downloads.discard(model_id)
                job = getattr(self, '_download_contexts', {}).pop(model_id, None)
            if job:
                try:
                    job.cleanup()
                except Exception as exc:
                    push.emit('log', {'level': 'warning', 'message': f'Download workspace retained: {exc}'})
            try:
                push.emit('model_download_finished', {'modelId': model_id})
            except Exception:
                # Delivery cannot undo completed cleanup or keep ownership held.
                pass

    def cancel_model_download(self, model_id):
        with self._render_lock:
            job = getattr(self, '_download_contexts', {}).get(model_id)
            entry = self.registry.get(model_id)
            if not job or not entry or entry.get('status') != 'downloading':
                return {'ok': False, 'message': 'That download is no longer running.'}
            job.request_stop()
            push.emit('model_download_stopping', {'modelId': model_id})
            return {'ok': True, 'message': 'Stopping; files remain protected until the transfer exits.'}

    def _run_local_download(self, model_id, stage_type, source_url):
        dest_dir = os.path.join(config.MODELS_DIR, "_downloads", model_id)
        filename = _safe_download_filename(source_url)
        dest_path = os.path.join(dest_dir, filename)
        try:
            selected = self.registry.get(model_id)
            if (selected or {}).get('request_preset') == 'f5tts' and source_url.rstrip('/') == 'https://huggingface.co/SWivid/F5-TTS':
                producer = download_with_progress(source_url, dest_path,
                    allow_patterns=['F5TTS_v1_Base/model_1250000.safetensors', 'F5TTS_v1_Base/vocab.txt', 'LICENSE*', 'README.md'],
                    revision='84e5a410d9cead4de2f847e7c9369a6440bdfaca')
            else:
                producer = download_with_progress(source_url, dest_path)
            try:
                for progress in producer:
                    if not self.registry.get(model_id):
                        continue
                    push.emit("model_download_progress", {"modelId": model_id, **progress})
            finally:
                # A yielded repository download can still own an internal
                # worker. Drain it even if notification/registry code fails,
                # before tracked finalization permits any destructive action.
                for _progress in producer:
                    pass

            if not self.registry.get(model_id):
                return
            check_cancelled()

            # dest_path is a directory for a whole-repo HF snapshot download
            # (see core/downloader.py's hf_repo_id_for_url()) and a plain
            # file otherwise - os.path.getsize() on a directory doesn't
            # raise on Windows but returns a meaningless small number (the
            # directory entry itself, not its contents), so it has to be
            # branched here rather than trusted blindly.
            if os.path.isdir(dest_path):
                file_size_bytes = sum(
                    os.path.getsize(os.path.join(root, f))
                    for root, _dirs, files in os.walk(dest_path) for f in files
                ) or None
            elif os.path.exists(dest_path):
                file_size_bytes = os.path.getsize(dest_path)
            else:
                file_size_bytes = None

            entry = self.registry.get(model_id)
            if stage_type == "voice" and entry.get('request_preset') != 'f5tts':
                _name, local_path = marketplace.install_downloaded_voice_model(dest_path)
            else:
                local_path = dest_path
            # file_size_bytes feeds the ETA/VRAM estimator (see
            # core/hardware_monitor.py) - a real, already-available number
            # that scales naturally with how heavy a model actually is,
            # instead of a hand-maintained per-model lookup table that
            # could never cover arbitrary user-added links.
            entry = self.registry.get(model_id)
            meta = dict(entry.get("meta") or {}) if entry else {}
            from core.model_contract import local_contract
            meta.update(local_contract(stage_type, local_path, entry.get('request_preset')))
            if stage_type == 'voice' and meta['adapter'] == 'rvc':
                from pathlib import Path
                indexes = list(Path(dest_dir).rglob('*.index'))
                if len(indexes) > 1:
                    raise ValueError('Voice archive has ambiguous retrieval indexes')
                if indexes:
                    meta['index_path'] = str(indexes[0])
            if file_size_bytes:
                meta["file_size_bytes"] = file_size_bytes
            job = current_job()
            if job:
                with job.lock:
                    job.check()
                    self.registry.update(model_id, local_path=local_path, status="installed", meta=meta)
            else:
                self.registry.update(model_id, local_path=local_path, status="installed", meta=meta)
            push.emit("model_installed", {"modelId": model_id, "stageType": stage_type})
        except Exception as e:
            self.registry.update(model_id, status="not_downloaded" if isinstance(e, RenderCancelled) else "error")
            push.emit("model_download_error", {"modelId": model_id, "message": str(e)})
        # Unregistered leftovers are retained for verified removal, not swept
        # using a registry-derived path outside the preview/ownership boundary.

    # --- file dialogs (native, via the pywebview window) ---
    def browse_video(self):
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=True,
            file_types=("Video Files (*.mp4;*.mov;*.avi;*.mkv)",),
        )
        return list(result) if result else []

    def browse_audio(self):
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("Audio Files (*.wav;*.mp3)",),
        )
        return result[0] if result else None

    def browse_subtitle(self):
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("Subtitle Files (*.srt)",),
        )
        return result[0] if result else None

    # --- node graph (Advanced view) ---
    @_graph_read
    def get_graph_definition(self):
        # Voice options aren't static - node_registry.py has no knowledge
        # of the model registry, so they're injected here at request time
        # from whatever voice models are actually installed.
        voice_options = [
            ('CLONED_USER', 'Use selected speech engine / reference audio'),
        ] + [
            (m["id"], m["display_name"])
            for m in self.registry.list("voice") if m["status"] == "installed"
        ]

        recognition = self.registry.get_active('stt')
        recognition_label = (recognition.get('display_name') or 'Selected recognition engine') if recognition else 'Built-in Whisper (CPU)'
        nodes = []
        for node_id, node in self.graph.nodes.items():
            spec = node.spec
            nodes.append({
                "id": node_id,
                "title": spec.title,
                "icon": spec.icon,
                "mutable": spec.mutable,
                "duplicable": spec.duplicable,
                "removable": node.removable,
                "headerColor": spec.header_color,
                "x": node.x,
                "y": node.y,
                "enabled": node.enabled,
                "params": [
                    {
                        "key": p.key, "kind": p.kind, "label": p.label,
                        "default": recognition_label if (spec.id == 'stt' and p.key == 'engine') else node.values.get(p.key),
                        "options": voice_options if (spec.id == "tts_rvc" and p.key == "voice") else p.options,
                    }
                    for p in spec.params
                ],
            })
        edges = [{"source": e.source_id, "target": e.target_id} for e in self.graph.edges]
        return {"nodes": nodes, "edges": edges}

    @_graph_change
    def set_node_enabled(self, node_id, enabled):
        node = self.graph.nodes.get(node_id)
        if not node or not node.spec.mutable or type(enabled) is not bool:
            return {'ok': False, 'message': 'Only optional nodes accept a boolean enabled value.'}
        node.enabled = enabled
        return {'ok': True}

    @_graph_change
    def set_node_param(self, node_id, key, value):
        node = self.graph.nodes.get(node_id)
        if not node:
            return {"ok": False}
        parameter = next((param for param in node.spec.params if param.key == key), None)
        if not parameter or parameter.kind == 'readonly':
            return {'ok': False, 'message': 'That node parameter is not editable.'}
        if parameter.kind == 'combo':
            choices = [choice[0] for choice in parameter.options]
            if node.spec.id == 'tts_rvc' and key == 'voice':
                choices = ['CLONED_USER'] + [entry['id'] for entry in self.registry.list('voice')
                                           if entry.get('status') == 'installed']
            if value not in choices:
                return {'ok': False, 'message': 'Select an available parameter option.'}
        elif parameter.kind == 'checkbox' and type(value) is not bool:
            return {'ok': False, 'message': 'That parameter requires a boolean.'}
        node.values[key] = value
        return {"ok": True}

    @_graph_change
    def add_node_instance(self, spec_id):
        """Adds a second (third, ...) instance of a duplicable stage - see
        NodeSpec.duplicable. Wired into the same edges as the original so
        it visually sits in the same stage of the pipeline; only "tts_rvc"
        is duplicable today, backing genuine multi-cast dubbing (see
        get_cast_list())."""
        from core.node_registry import SPECS

        spec = SPECS.get(spec_id)
        if not spec or not spec.duplicable:
            return {"ok": False, "message": f"'{spec_id}' can't be duplicated."}

        # A deleted middle instance must not cause an existing ID to be reused.
        suffixes = [int(nid[len(spec_id) + 1:]) for nid in self.graph.nodes
                    if nid.startswith(f'{spec_id}_') and nid[len(spec_id) + 1:].isdigit()]
        new_id = f"{spec_id}_{max([1, *suffixes]) + 1}"

        base = self.graph.nodes[spec_id]
        new_node = self.graph.add_node(new_id, spec, base.x, base.y + 140, removable=True)
        new_node.enabled = True

        for edge in list(self.graph.edges):
            if edge.source_id == spec_id:
                self.graph.connect(new_id, edge.target_id)
            if edge.target_id == spec_id:
                self.graph.connect(edge.source_id, new_id)

        return {"ok": True, "nodeId": new_id}

    @_graph_change
    def remove_node_instance(self, node_id):
        return {"ok": self.graph.remove_node(node_id)}

    @_graph_change
    def set_node_position(self, node_id, x, y):
        node = self.graph.nodes.get(node_id)
        if not node or any(type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 100000 for value in (x, y)):
            return {'ok': False, 'message': 'Invalid node position.'}
        node.x, node.y = x, y
        return {'ok': True}

    @_graph_read
    def get_cast_list(self):
        """All Voice node instances' chosen voices, oldest first - the
        multi-cast list ReflowPipeline.process_video_gen() cycles through
        per segment. A single-entry (or empty) result means the graph
        hasn't been extended past the default one Voice node, so callers
        should prefer the Dashboard's own single voice choice instead of
        this - see bridge/api.py's _template_kwargs()."""
        voice_nodes = sorted(
            (n for n in self.graph.nodes.values() if n.spec.id == "tts_rvc"),
            key=lambda n: 1 if n.id == 'tts_rvc' else int(n.id.rsplit('_', 1)[1]),
        )
        return [n.values.get("voice", "CLONED_USER") for n in voice_nodes]

    # --- startup / maintenance ---
    def run_integrity_check(self):
        try:
            from core.integrity import IntegrityDoctor
            unavailable = IntegrityDoctor().check_libraries()
            return {"ok": not unavailable, "unavailable_libraries": unavailable,
                    "message": ('Desktop imports verified. Selected engines and model assets are checked separately.'
                                if not unavailable else 'Unavailable runtime libraries: ' + ', '.join(item['module'] for item in unavailable))}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def factory_reset(self, preview_token=None):
        with self._render_lock:
            return self._execute_deletion("reset", preview_token)

    # --- render lifecycle ---
    def list_pipeline_templates(self):
        from pipeline import ReflowPipeline
        return ReflowPipeline.PIPELINE_TEMPLATES

    def _session_state(self):
        if not hasattr(self, '_session'):
            self._session = SessionState()
        return self._session

    def _snapshot(self, changed=False):
        with self._session_state()._lock:
            return self._session_state().snapshot(
                self.queue_manager.get_items(), self.queue_manager.is_paused(),
                getattr(self, '_render_busy', False) or getattr(self, '_active_job', None), changed)

    def _publish_session(self):
        snapshot = self._snapshot(changed=True)
        try:
            push.emit('session_state', snapshot)
        except Exception:
            # The next snapshot can recover a lost UI notification.
            pass

    def get_session_state(self):
        with self._render_lock:
            snapshot = self._snapshot()
        self._flush_persistence_warnings()
        return snapshot

    def _emit_render(self, event, payload):
        with self._session_state()._lock:
            self._session_state().event(event, payload)
            item_id = getattr(self, '_current_queue_item', None)
            if item_id and event == 'progress' and self._session_state().render['status'] != 'stopping':
                self.queue_manager.update_item(item_id, progress=payload['percent'], status_text=payload['status'])
            self._publish_session()
        # Preserve legacy consumers while the UI uses the versioned snapshot.
        push.emit(event, payload)

    def _start_rejection(self):
        if getattr(self, '_runtime_check_busy', False):
            return 'A runtime check is running. Wait for it to finish before starting a job.'
        previous = getattr(self, '_active_job', None)
        if previous and previous.processes:
            return 'Previous render processes have not exited; workspace retained.'
        if self._render_thread and self._render_thread.is_alive():
            return 'A render is already running or finishing cleanup.'
        return None

    def _start_worker(self, input_path, params, template_id, queue_item_id):
        self._render_killed = False
        self._render_busy = True
        session = self._session_state()
        with session._lock:
            previous_render = deepcopy(session.render)
            previous_updated_at = session.updated_at
        self._session_state().event('render_started', {'inputPath': input_path})
        previous_state = self._render_thread
        try:
            self._render_thread = threading.Thread(
                target=self._worker_entry, args=(input_path, deepcopy(params), template_id, queue_item_id), daemon=True)
            self._publish_session()
            self._render_thread.start()
        except Exception as exc:
            self._render_thread = previous_state
            self._render_busy = False
            with session._lock:
                session.render = previous_render
                session.updated_at = previous_updated_at
            self._publish_session()
            return {'ok': False, 'message': f'Could not start worker: {exc}'}
        return {'ok': True}

    def _worker_entry(self, *args):
        try:
            self._run_render(*args)
        except Exception as exc:
            self.queue_manager.pause_after_storage_error()
            self._emit_render('render_error', {'message': 'Worker stopped before batch advancement: ' + str(exc)})
        finally:
            with self._render_lock:
                self._render_busy = bool(getattr(self, '_active_job', None))
                self._current_queue_item = None
                self._publish_session()

    def start_render(self, input_path, params, template_id="video_dub", queue_item_id=None):
        with self._render_lock:
            rejection = self._start_rejection()
            if rejection:
                return {'ok': False, 'message': rejection}
            if not isinstance(input_path, str) or not input_path.strip() or not isinstance(params, dict):
                return {'ok': False, 'message': 'An input path and render settings are required.'}
            if template_id not in ('video_dub', 'video_dub_lipsync', 'audio_dub', 'subtitle_translate'):
                return {'ok': False, 'message': 'Unknown pipeline template.'}
            checkpoint = self.queue_manager.checkpoint()
            if queue_item_id:
                item = next((it for it in self.queue_manager.get_items() if it['id'] == queue_item_id), None)
                if not item or item['status'] != 'queued' or item['input_path'] != input_path:
                    return {'ok': False, 'message': 'That queued job is unavailable.'}
                params, template_id = item['params'], item['template_id']
                self.queue_manager.update_item(queue_item_id, status='processing')
            result = self._start_worker(input_path, params, template_id, queue_item_id)
            if not result['ok']:
                self.queue_manager.restore(checkpoint)
                self._publish_session()
            return result

    def stop_render(self):
        with self._render_lock:
            job = getattr(self, "_active_job", None)
            running = getattr(self, '_render_busy', self._render_thread and self._render_thread.is_alive())
            if not job and not running:
                return {"ok": True, "stopping": False}
            self._render_killed = True
            if job:
                job.request_stop()
            self.queue_manager.set_paused(True)
            self._emit_render("render_stopping", {"message": "Stopping… waiting for active work to exit."})
        return {"ok": True, "stopping": True}

    # --- single-voice audio cue review ---
    def _cue_store(self):
        from core.cue_review import ReviewStore
        return ReviewStore(config.OUTPUT_PATH)

    def list_cue_reviews(self):
        try:
            return {'ok': True, 'reviews': self._cue_store().list()}
        except Exception as exc:
            return {'ok': False, 'message': str(exc), 'reviews': []}

    def get_cue_review(self, identifier):
        try:
            return {'ok': True, 'review': self._cue_store().public(identifier)}
        except Exception as exc:
            return {'ok': False, 'message': str(exc)}

    def edit_review_cue(self, identifier, revision, index, source_text, text, start=None, end=None):
        with self._render_lock:
            if self._deletion_busy():
                return {'ok': False, 'message': 'Wait for active work to finish before editing.'}
            try:
                return {'ok': True, 'review': self._cue_store().edit(identifier, revision, index, source_text, text, start, end)}
            except Exception as exc:
                return {'ok': False, 'message': str(exc)}

    def estimate_review_timing(self, identifier, revision, index):
        with self._render_lock:
            if self._deletion_busy():
                return {'ok': False, 'message': 'Wait for active work to finish before checking timing.'}
            try:
                from types import SimpleNamespace
                from core.cue_review import estimate_timing
                budget = estimate_timing(self._cue_store(), SimpleNamespace(registry=self.registry),
                                         identifier, revision, index, self.settings)
                return {'ok': True, **budget}
            except Exception as exc:
                return {'ok': False, 'message': str(exc)}

    def accept_review_cue(self, identifier, revision, index):
        with self._render_lock:
            if self._deletion_busy():
                return {'ok': False, 'message': 'Wait for active work to finish before accepting a take.'}
            try:
                return {'ok': True, 'review': self._cue_store().accept(identifier, revision, index)}
            except Exception as exc:
                return {'ok': False, 'message': str(exc)}

    def combine_review_cues(self, identifier, revision, index):
        with self._render_lock:
            if self._deletion_busy():
                return {'ok': False, 'message': 'Wait for active work to finish before combining lines.'}
            try:
                return {'ok': True, 'review': self._cue_store().combine(identifier, revision, index)}
            except Exception as exc:
                return {'ok': False, 'message': str(exc)}

    def get_review_audio(self, identifier, index, accepted=False):
        try:
            if type(accepted) is not bool:
                raise ValueError('Invalid take selection')
            return {'ok': True, 'audio': self._cue_store().audio(identifier, index, accepted)}
        except Exception as exc:
            return {'ok': False, 'message': str(exc)}

    def start_cue_review(self, input_path, params):
        with self._render_lock:
            rejection = self._start_rejection()
            if rejection:
                return {'ok': False, 'message': rejection}
            try:
                if not isinstance(input_path, str) or not os.path.isfile(input_path) or not isinstance(params, dict):
                    raise ValueError('Select an audio file and review settings')
                frozen = deepcopy(params)
                frozen['review_video'] = os.path.splitext(input_path)[1].lower() in ('.mp4','.mkv','.mov','.webm','.avi','.m4v')
                frozen['cast_list'] = self._resolve_cast_list(frozen)
                if len(frozen['cast_list']) != 1:
                    raise ValueError('Cue review currently supports one voice. Remove extra voice nodes first.')
                frozen['_review_action'] = 'prepare'
                return self._start_worker(input_path, frozen, 'audio_dub', None)
            except Exception as exc:
                return {'ok': False, 'message': str(exc)}

    def get_review_source_audio(self, identifier, index):
        try:
            return {'ok': True, 'audio': self._cue_store().source_audio(identifier, index)}
        except Exception as exc:
            return {'ok': False, 'message': str(exc)}

    def start_review_action(self, identifier, revision, action, index=None):
        with self._render_lock:
            rejection = self._start_rejection()
            if rejection:
                return {'ok': False, 'message': rejection}
            try:
                if action not in ('generate', 'translate', 'adapt', 'supervise', 'render'):
                    raise ValueError('Unknown review action')
                store = self._cue_store()
                manifest = store.load(identifier, revision)
                if action != 'render':
                    store.cue(manifest, index)
                params = {'_review_action': action, '_review_id': identifier,
                          '_review_revision': revision, '_review_index': index}
                return self._start_worker(manifest['name'], params, 'audio_dub', None)
            except Exception as exc:
                return {'ok': False, 'message': str(exc)}

    def get_interrupted_render(self):
        """Checked once by App.tsx right after boot - a non-None result
        means the app didn't shut down cleanly last time during a render
        (see core/render_state.py). Restart uses the same input/params and
        may reuse verified recognition/translation checkpoints for supported
        selected local engines. Other stages run again."""
        with self._render_lock:
            if getattr(self, '_render_busy', False) or getattr(self, '_active_job', None) or (self._render_thread and self._render_thread.is_alive()):
                return None
            record = render_state.get_interrupted(warning=self._queue_persistence_warning)
            if record and record.get('queue_item_id'):
                item = next((it for it in self.queue_manager.get_items() if it['id'] == record['queue_item_id']), None)
                if item and item['status'] in ('completed', 'failed', 'cancelled'):
                    return None  # Crash after terminal queue commit, before marker cleanup.
            return record

    def discard_interrupted_render(self, recovery_token):
        with self._render_lock:
            if self._deletion_busy():
                return {'ok': False, 'message': 'Wait for active work to finish.'}
            try:
                record = render_state.get_interrupted()
                if record and record['recovery_token'] != recovery_token:
                    return {'ok': False, 'message': 'Recovery record changed; refresh the offer.'}
                item_id = record.get('queue_item_id') if record else None
                if item_id:
                    item = next((it for it in self.queue_manager.get_items() if it['id'] == item_id), None)
                    if item and item['status'] == 'queued':
                        self.queue_manager.update_item(item_id, status='cancelled', status_text='Recovery discarded')
                ok = render_state.discard(recovery_token)
                self._publish_session()
                return {'ok': ok, 'message': None if ok else 'Recovery record changed; refresh the offer.'}
            except (ValueError, OSError) as exc:
                return {'ok': False, 'message': str(exc)}

    def resume_interrupted_render(self, recovery_token):
        """Restart the offered job once; other restored batch jobs stay paused."""
        with self._render_lock:
            rejection = self._start_rejection()
            if rejection:
                return {'ok': False, 'message': rejection}
            try:
                record = render_state.get_interrupted(warning=self._queue_persistence_warning)
                if not record or record['recovery_token'] != recovery_token:
                    return {'ok': False, 'message': 'Recovery record changed; refresh the offer.'}
                item_id = record.get('queue_item_id')
                if item_id:
                    item = next((it for it in self.queue_manager.get_items() if it['id'] == item_id), None)
                    if not item or item['status'] != 'queued' or any(item[key] != record[key] for key in ('input_path', 'params', 'template_id')):
                        return {'ok': False, 'message': 'Recovered queue job changed or is unavailable. Review the queue.'}
                checkpoint = self.queue_manager.checkpoint()
                if item_id:
                    self.queue_manager.prepare_recovery(item_id)
                result = self._start_worker(record['input_path'], record['params'], record['template_id'], item_id)
                if not result['ok']:
                    self.queue_manager.restore(checkpoint)
                    self._publish_session()
                return result
            except (ValueError, OSError) as exc:
                return {'ok': False, 'message': str(exc)}

    def _run_render(self, input_path, params, template_id, queue_item_id=None):
        while True:
            terminal_recorded = False
            marker_written = False
            job = None
            try:
                with self._render_lock:
                    if self._render_killed:
                        break
                    job = RenderContext(config.TEMP_PATH)
                    self._active_job = job
                    self._current_queue_item = queue_item_id
                if queue_item_id:
                    self.queue_manager.update_item(queue_item_id, status="processing", progress=0,
                                                   status_text="Rendering...", error=None, output_path=None)
                self._publish_session()
                render_state.mark_started(input_path, params, template_id, warning=self._queue_persistence_warning, queue_item_id=queue_item_id)
                marker_written = True
                with bind_job(job):
                    output_path = self._run_render_inner(input_path, params, template_id)
                if params.get('_review_action') in ('prepare', 'generate', 'translate'):
                    output_path = None  # A review draft/take is not a final media output.
                with self._render_lock:
                    if not self._render_killed:
                        if queue_item_id:
                            self.queue_manager.update_item(queue_item_id, status="completed", progress=100,
                                                           status_text="Completed", output_path=output_path)
                        terminal_recorded = True
                        self._emit_render("render_finished", {"outputPath": output_path})
            except Exception as e:
                with self._render_lock:
                    if not self._render_killed:
                        if queue_item_id:
                            self.queue_manager.update_item(queue_item_id, status="failed", error=str(e), status_text="Failed")
                        terminal_recorded = True
                        self._emit_render("render_error", {"message": str(e)})
            finally:
                if queue_item_id and self._render_killed and not terminal_recorded:
                    self.queue_manager.update_item(queue_item_id, status="cancelled", status_text="Cancelled")
                if job:
                    try:
                        if self._render_killed or self.settings.get("auto_cleanup_temp"):
                            job.cleanup()
                    except Exception as e:
                        push.emit("log", {"level": "warning", "message": f"Temporary cleanup failed; retained {job.workspace}: {e}"})
                try:
                    if marker_written:
                        render_state.clear()
                except Exception as e:
                    push.emit("log", {"level": "warning", "message": f"Could not clear render state: {e}"})
                with self._render_lock:
                    if job and job.processes:
                        push.emit("log", {"level": "warning", "message": "Owned processes have not exited; render remains blocked and workspace retained."})
                        return
                    self._active_job = None
            if self._render_killed:
                break
            # Standalone audio/subtitle/video renders do not consume queued jobs.
            with self._render_lock:
                if self._render_killed:
                    break
                next_item = self.queue_manager.claim_next() if queue_item_id else None
            if next_item is None:
                self._publish_session()
                return
            input_path, params = next_item.input_path, next_item.params
            template_id, queue_item_id = next_item.template_id, next_item.id
            push.emit("log", {"level": "info", "message": f"[QUEUE] Auto-advancing to next queued item: {queue_item_id}"})
        self._emit_render("render_stopped", {})

    def _resolve_cast_list(self, params):
        """A cast_list with 2+ entries means the user explicitly added
        extra Voice nodes on the graph (get_cast_list()) - genuine
        multi-cast, each entry a different actor's voice. Otherwise fall
        back to the Dashboard's own single voice dropdown, unchanged from
        before this feature existed - adding this never alters the
        single-voice default path."""
        cast_list = self.get_cast_list()
        return cast_list if len(cast_list) > 1 else [params["voice"]]

    def _template_kwargs(self, template_id, params):
        """Maps the one RenderParams shape the frontend always sends into
        the kwargs each pipeline template actually accepts - so the
        frontend doesn't need a different payload shape per template."""
        from core.pipeline_contracts import template_kwargs
        return template_kwargs(template_id, params, self._resolve_cast_list)

    # --- queue API ---
    def add_queue_item(self, input_path, params=None, template_id="video_dub"):
        with self._render_lock:
            item = self.queue_manager.add_item(input_path, params, template_id)
            self._publish_session()
            return item

    def add_queue_drafts(self, paths):
        with self._render_lock:
            if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not p.strip() for p in paths):
                return {'ok': False, 'message': 'Select valid input paths.'}
            for path in paths:
                self.queue_manager.add_item(path)
            self._publish_session()
            return {'ok': True}

    def _begin_batch(self, params=None, template_id=None, expected_ids=None):
        rejection = self._start_rejection()
        if rejection:
            return {'ok': False, 'message': rejection}
        if expected_ids is not None:
            pending = [it['id'] for it in self.queue_manager.get_items() if it['status'] in ('draft', 'queued')]
            if not isinstance(expected_ids, list) or expected_ids != pending:
                return {'ok': False, 'message': 'Pending jobs changed. Review the batch again.'}
        checkpoint = self.queue_manager.checkpoint()
        if params is not None:
            if not isinstance(params, dict) or template_id not in ('video_dub', 'video_dub_lipsync'):
                return {'ok': False, 'message': 'Video batch settings and template are required.'}
            params = deepcopy(params)
            if 'voice' in params:
                params['cast_list'] = self._resolve_cast_list(params)
        try:
            first = self.queue_manager.prepare_batch(params, template_id)
        except (ValueError, OSError) as exc:
            return {'ok': False, 'message': 'Batch was not saved: ' + str(exc)}
        if not first:
            self.queue_manager.restore(checkpoint)
            return {'ok': False, 'message': 'No accepted jobs to resume.' if params is None else 'No pending video jobs.'}
        result = self._start_worker(first.input_path, first.params, first.template_id, first.id)
        if not result['ok']:
            self.queue_manager.restore(checkpoint)
            self._publish_session()
        return result

    def start_queue_batch(self, params, template_id='video_dub', expected_ids=None):
        with self._render_lock:
            return self._begin_batch(params, template_id, expected_ids)

    def resume_queue_batch(self):
        with self._render_lock:
            return self._begin_batch()

    def remove_queue_item(self, item_id):
        with self._render_lock:
            if item_id == getattr(self, '_current_queue_item', None) and (getattr(self, '_render_busy', False) or getattr(self, '_active_job', None)):
                return {'ok': False, 'message': 'The active job is still finishing cleanup.'}
            result = self.queue_manager.remove_item(item_id)
            self._publish_session()
            return {"ok": result, 'message': None if result else 'Active or missing jobs cannot be removed.'}

    def clear_completed_queue(self):
        with self._render_lock:
            self.queue_manager.clear_completed(getattr(self, '_current_queue_item', None))
            self._publish_session()
            return {"ok": True}

    def get_queue_items(self):
        return self.queue_manager.get_items()

    def set_queue_paused(self, paused):
        with self._render_lock:
            self.queue_manager.set_paused(bool(paused))
            self._publish_session()
            return {"ok": True}

    # --- benchmark API ---
    def run_hardware_benchmark(self, device_id=None):
        return self.monitor.run_benchmark(device_id)

    def _run_render_inner(self, input_path, params, template_id="video_dub"):
        generator = None
        try:
            self._emit_render("render_started", {"inputPath": input_path})
            push.emit("log", {"level": "info", "message": f"[QUEUE] Starting: {os.path.basename(input_path)}"})
            from pipeline import ReflowPipeline
            pipeline = ReflowPipeline()
            pipeline.source_language_callback = lambda payload: (
                self._emit_render("source_language", payload) if not self._render_killed else None)

            if params.get('_review_action'):
                from core.cue_review import prepare, operate
                progress = lambda percent, status: self._emit_render('progress', {'percent': percent, 'status': status})
                store = self._cue_store()
                if params['_review_action'] == 'prepare':
                    return prepare(store, pipeline, input_path, self._template_kwargs('audio_dub', params),
                                   self.settings, progress)
                return operate(store, pipeline, params.get('_review_id'), params.get('_review_revision'),
                               params['_review_action'], params.get('_review_index'), self.settings, progress)

            kwargs = self._template_kwargs(template_id, params)
            generator = pipeline.run(template_id, input_path, kwargs)

            final_result = None
            while True:
                check_cancelled()
                try:
                    percent, status, result = next(generator)
                except StopIteration:
                    break
                check_cancelled()
                if self._render_killed:
                    return
                self._emit_render("progress", {"percent": percent, "status": status})
                stage_id = status_to_stage_id(status)
                if stage_id:
                    self._emit_render("stage", {"stageId": stage_id})
                if result:
                    final_result = result
                if "SEG" not in status:
                    push.emit("log", {"level": "info", "message": f"[PHASE] {status}"})

            if self._render_killed:
                return None
            if not final_result:
                raise RuntimeError("Process finished without output.")
            if not os.path.isfile(final_result) or os.path.getsize(final_result) == 0:
                raise RuntimeError(f"Process returned a missing or empty output: {final_result}")
            return final_result
        finally:
            # Close a cancelled generator so its own finally blocks can run.
            if generator is not None:
                generator.close()
            manifest_path = getattr(locals().get('pipeline'), 'last_manifest_path', None)
            if isinstance(manifest_path, str):
                push.emit('log', {'level': 'info', 'message': '[RUN RECORD] ' + manifest_path})
            if params.get('_review_action') and 'pipeline' in locals():
                pipeline.clear_vram()
