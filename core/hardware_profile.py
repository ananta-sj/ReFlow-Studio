"""Persisted snapshot of this machine's hardware - captured once (on first
boot, see App.tsx's capture_hardware_profile() call) and reused by
bridge/api.py's "Best For This Device" hint on Marketplace recommendations
(core/recommended_models.py) so the Marketplace doesn't need to re-run
hardware detection every time it renders. Same simple JSON-file-next-to-
config.py pattern as core/settings.py and core/model_registry.py.

Deliberately a separate file, not folded into settings.json: this is a
cached hardware *fact*, not a user preference (settings.py's own docstring
scopes it to preferences only), and re-detecting it later (e.g. after a
hardware upgrade) shouldn't touch anything the user has configured.
"""

import os
import math
from copy import deepcopy
from core.json_store import JsonStore, require

import config

PROFILE_PATH = os.path.join(config.BASE_DIR, "hardware_profile.json")


def _validate(profile):
    require(isinstance(profile, dict), 'Hardware profile must be an object')
    require(isinstance(profile.get('cpu_name'), str), 'Invalid CPU name')
    best = profile.get('best_device')
    require(isinstance(best, dict), 'Invalid best device')
    for field in ('id', 'kind', 'name'):
        require(isinstance(best.get(field), str), 'Invalid device ' + field)
    for value in (profile.get('ram_total_gb'), best.get('vram_total_mb')):
        require(value is None or type(value) in (float, int) and math.isfinite(value) and value >= 0, 'Invalid hardware capacity')
    return profile


class HardwareProfileStore:
    def __init__(self, warning=None):
        self._store = JsonStore(PROFILE_PATH, None, _validate, warning)
        self._profile = self._load()

    def _load(self):
        return self._store.read()

    def get(self):
        with self._store.locked():
            self._profile = self._load()
            return deepcopy(self._profile)

    def capture(self, monitor, force=False):
        """Detects and saves the current machine's profile: the best
        device this app would actually pick by default (see
        HardwareMonitor.default_device_id() - the same logic real render
        jobs use, so this reflects what a job would actually get, not just
        whatever's physically present but undriveable) plus total system
        RAM. A no-op returning the existing profile unless force=True, so
        repeated calls (e.g. every app boot) are cheap and don't need their
        own "already captured" guard on the caller's side."""
        with self._store.locked():
            return self._capture_locked(monitor, force)

    def _capture_locked(self, monitor, force):
        previous = self._load()
        if previous is not None and not force:
            self._profile = previous
            return deepcopy(previous)

        best_id = monitor.default_device_id()
        best_device = next((d for d in monitor.devices if d.id == best_id), None)
        ram_total_gb = monitor.sample(best_id).get("ram_total_gb")

        candidate = {
            "cpu_name": monitor.cpu_name,
            "ram_total_gb": ram_total_gb,
            "best_device": {
                "id": best_device.id if best_device else "cpu",
                "kind": best_device.kind if best_device else "cpu",
                "name": best_device.name if best_device else monitor.cpu_name,
                "vram_total_mb": best_device.vram_total_mb if best_device else None,
            },
        }
        self._profile = self._store.replace(candidate)
        return deepcopy(self._profile)
