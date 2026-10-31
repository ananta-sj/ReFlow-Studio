"""Hardware detection & live telemetry: CPU/GPU/RAM info, per-device VRAM
sampling, and a rough ETA heuristic for the render telemetry panel.

Kept dependency-light on purpose (only psutil + optional torch, both
already required elsewhere) - GPU enumeration beyond what torch can see is
best-effort and informational only, matching the rest of this codebase's
"degrade gracefully if the optional bit isn't available" style.
"""

import os
import platform
import subprocess

import psutil

try:
    import torch
except (ImportError, OSError, RuntimeError):
    torch = None


class GPUDevice:
    def __init__(self, id, name, kind, backend, vram_total_mb=None):
        self.id = id                  # "cuda:0", "mps", "cpu", "other:<name>"
        self.name = name
        self.kind = kind              # "dedicated" | "integrated" | "cpu"
        self.backend = backend        # "cuda" | "mps" | "cpu" | "unsupported"
        self.vram_total_mb = vram_total_mb

    def label(self):
        tag = {"dedicated": "Dedicated", "integrated": "Integrated", "cpu": "CPU Fallback"}.get(self.kind, self.kind)
        vram = f" · {self.vram_total_mb / 1024:.1f}GB" if self.vram_total_mb else ""
        usable = "" if self.backend != "unsupported" else " (detected, not accelerated)"
        return f"{self.name} [{tag}]{vram}{usable}"


# Rough seconds-of-processing per second-of-source-video, CPU baseline.
# These are order-of-magnitude guesses (see README's own CPU timing notes),
# not measured benchmarks - the ETA is explicitly labelled as an estimate.
_STAGE_COST = {
    "stt": 0.5, "translate": 0.05, "tts_rvc": 1.5,
    "lipsync": 3.0, "enhance": 8.0, "content_filter": 1.0, "mix": 0.1,
    "separate": 4.0,
    # Only added to the estimate when a profanity_filter model is actually
    # active (see bridge/api.py's _active_stages) - an extra LLM rewrite
    # pass per segment, roughly the same order of cost as "translate".
    "profanity_filter": 0.05,
}
_DEVICE_SPEEDUP = {"dedicated": 0.2, "integrated": 0.6, "cpu": 1.0}

# AirLLM trades speed for low VRAM by streaming every transformer layer
# from disk on every forward pass - dramatically slower than the default
# M2M100/Ollama translation path (see core/providers/translation/
# airllm_local.py), so it needs its own cost/VRAM numbers rather than
# sharing "translate"'s. bridge/api.py's _model_resource_override() only
# applies these when the active translation model is actually AirLLM.
AIRLLM_TRANSLATE_COST = 6.0
AIRLLM_TRANSLATE_VRAM_MB = 400  # only ever holds a couple of layers resident at once

# Rough VRAM footprint per stage's model weights, in MB, when resident on a
# GPU. Ballpark figures from the actual checkpoint sizes this app downloads
# (GFPGAN ~350MB, XTTS ~2GB, Wav2Lip ~450MB) plus working-memory overhead -
# a budget estimate, not a measurement.
_STAGE_VRAM_MB = {
    "tts_rvc": 2600, "lipsync": 900, "enhance": 1400, "content_filter": 500,
}


class HardwareMonitor:
    def __init__(self):
        self.cpu_name = self._detect_cpu_name()
        self.cpu_cores = psutil.cpu_count(logical=True) or 1
        self.devices = self._detect_devices()

    def _detect_cpu_name(self):
        # platform.processor() returns a raw ID string on Windows (e.g.
        # "Intel64 Family 6 Model 186 Stepping 2, GenuineIntel") - try a
        # friendlier marketing name first, matching what the GPU query gives.
        if platform.system() == "Windows":
            try:
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"],
                    stderr=subprocess.DEVNULL, timeout=5,
                ).decode(errors="ignore").strip()
                if out:
                    return out.splitlines()[0].strip()
            except (subprocess.SubprocessError, OSError, FileNotFoundError):
                pass

        name = platform.processor() or platform.machine()
        return name or "Unknown CPU"

    @staticmethod
    def _guess_adapter_kind(name):
        """Name-based heuristic for adapters torch can't enumerate itself.
        Not authoritative, just enough to avoid mislabeling e.g. an NVIDIA
        RTX/GTX or AMD Radeon RX card (dedicated) as "integrated" just
        because it showed up in the same OS query as the iGPU."""
        lowered = name.lower()
        integrated_markers = ("intel(r) uhd", "intel(r) iris", "intel(r) hd graphics", "radeon(tm) graphics")
        if any(marker in lowered for marker in integrated_markers):
            return "integrated"
        # AMD's mobile APU GPUs are named like "Radeon 780M/680M/660M".
        if "radeon" in lowered and lowered.rstrip().endswith("m"):
            return "integrated"
        if "nvidia" in lowered or "geforce" in lowered or "radeon rx" in lowered or "quadro" in lowered:
            return "dedicated"
        return "integrated"

    def _detect_devices(self):
        devices = []
        seen_names = set()

        if torch is not None and torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                devices.append(GPUDevice(
                    id=f"cuda:{i}", name=props.name, kind="dedicated", backend="cuda",
                    vram_total_mb=props.total_memory // (1024 * 1024),
                ))
                seen_names.add(props.name)
        elif torch is not None and getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available():
            devices.append(GPUDevice(id="mps", name="Apple Silicon GPU", kind="integrated", backend="mps"))
            seen_names.add("Apple Silicon GPU")

        # nvidia-smi sees real VRAM totals even when torch has no CUDA
        # build available - without this, an NVIDIA GPU that's only
        # reachable via the WMI "other adapter" fallback below reports no
        # VRAM at all, which reads as "this GPU has no VRAM" rather than
        # "we couldn't measure it."
        nvidia_smi_snapshot = self._nvidia_smi_snapshot()

        for name in self._detect_other_adapters():
            if name not in seen_names:
                kind = self._guess_adapter_kind(name)
                vram_total_mb = nvidia_smi_snapshot.get(name, (None, None))[0]
                devices.append(GPUDevice(
                    id=f"other:{name}", name=name, kind=kind, backend="unsupported",
                    vram_total_mb=vram_total_mb,
                ))
                seen_names.add(name)

        devices.append(GPUDevice(id="cpu", name=self.cpu_name, kind="cpu", backend="cpu"))
        return devices

    def _detect_other_adapters(self):
        """Best-effort listing of adapters torch itself can't drive (e.g. an
        integrated GPU sitting next to a dedicated one). Informational only."""
        names = []
        system = platform.system()
        try:
            if system == "Windows":
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                    stderr=subprocess.DEVNULL, timeout=5,
                ).decode(errors="ignore")
                names = [n.strip() for n in out.splitlines() if n.strip()]
            elif system == "Darwin":
                out = subprocess.check_output(
                    ["system_profiler", "SPDisplaysDataType"], stderr=subprocess.DEVNULL, timeout=5
                ).decode(errors="ignore")
                names = [l.split(":", 1)[-1].strip() for l in out.splitlines() if "Chipset Model" in l]
            elif system == "Linux":
                out = subprocess.check_output(["lspci"], stderr=subprocess.DEVNULL, timeout=5).decode(errors="ignore")
                names = [l.split(":", 2)[-1].strip() for l in out.splitlines() if "VGA" in l or "3D controller" in l]
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        return names

    @staticmethod
    def _nvidia_smi_snapshot():
        """{adapter name: (total_mb, used_mb)} via nvidia-smi, which reports
        real VRAM figures whether or not torch has a CUDA build available -
        unlike Windows' WMI AdapterRAM, which is well known to misreport
        adapters with more than 4GB VRAM. Returns {} on any failure
        (nvidia-smi not on PATH, no NVIDIA GPU, timeout, etc.) - this is
        pure enrichment, never required."""
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL, timeout=5,
            ).decode(errors="ignore")
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            return {}

        snapshot = {}
        for line in out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 3:
                continue
            name, total, used = parts
            try:
                snapshot[name] = (int(total), int(used))
            except ValueError:
                continue
        return snapshot

    def default_device_id(self):
        # Prefer a dedicated GPU torch can actually drive; a dedicated card
        # that only showed up via the OS adapter query (backend="unsupported")
        # would just silently fall back to CPU on every run, so it's a worse
        # default than picking CPU explicitly.
        for d in self.devices:
            if d.kind == "dedicated" and d.backend != "unsupported":
                return d.id
        for d in self.devices:
            if d.backend == "mps":
                return d.id
        return "cpu"

    def device_kind(self, device_id):
        for d in self.devices:
            if d.id == device_id:
                return d.kind
        return "cpu"

    def sample(self, device_id=None):
        """Live utilization snapshot for the status bar / telemetry panel."""
        cpu_percent = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        ram_used_gb = (vm.total - vm.available) / (1024 ** 3)
        ram_total_gb = vm.total / (1024 ** 3)

        vram_used_mb = vram_total_mb = None
        if device_id and device_id.startswith("cuda:") and torch is not None and torch.cuda.is_available():
            try:
                idx = int(device_id.split(":")[1])
                vram_used_mb = torch.cuda.memory_reserved(idx) // (1024 * 1024)
                vram_total_mb = torch.cuda.get_device_properties(idx).total_memory // (1024 * 1024)
            except (RuntimeError, ValueError, IndexError, AssertionError):
                pass
        elif device_id and device_id.startswith("other:") and "nvidia" in device_id.lower():
            # An NVIDIA GPU torch can't drive directly (no CUDA build) can
            # usually still be read live via nvidia-smi - real numbers
            # beat leaving the panel blank for a GPU that's clearly there.
            name = device_id.split(":", 1)[1]
            total, used = self._nvidia_smi_snapshot().get(name, (None, None))
            vram_total_mb, vram_used_mb = total, used

        return {
            "cpu_percent": cpu_percent,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "vram_used_mb": vram_used_mb,
            "vram_total_mb": vram_total_mb,
        }

    def base_stage_cost(self, stage):
        """The flat, model-agnostic cost ratio for a pipeline stage - the
        fallback bridge/api.py's _model_resource_override() uses when
        nothing more specific is known about the active model (not yet
        downloaded, or a kind with no size to go on)."""
        return _STAGE_COST.get(stage, 0.0)

    def base_stage_vram_mb(self, stage):
        return _STAGE_VRAM_MB.get(stage, 0)

    def estimate_eta_seconds(self, video_duration_sec, stages, device_id="cpu", stage_cost_overrides=None, stage_device_overrides=None):
        """Rough heuristic ETA - actual time varies a lot by hardware/content.
        stage_cost_overrides lets a caller swap in a different cost ratio
        for specific stages - bridge/api.py builds these from whichever
        model is actually active per stage (see _model_resource_override()),
        so a heavier/lighter model than the flat default genuinely changes
        the estimate instead of every model of a given stage type costing
        the same."""
        kind = self.device_kind(device_id)
        factor = _DEVICE_SPEEDUP.get(kind, 1.0)
        overrides = stage_cost_overrides or {}
        routes = stage_device_overrides or {}
        total_ratio = sum((overrides[s] if s in overrides else _STAGE_COST.get(s, 0.0)) *
                          (_DEVICE_SPEEDUP.get(self.device_kind(routes[s]), 1.0) if s in routes else factor)
                          for s in stages)
        return max(5, int(video_duration_sec * total_ratio))

    def estimate_peak_vram_mb(self, stages, device_id="cpu", stage_vram_overrides=None):
        """Rough VRAM budget estimate for the enabled stages - a planning
        number, not a live measurement (see sample() for that). See
        estimate_eta_seconds() for what stage_vram_overrides is."""
        if self.device_kind(device_id) == "cpu":
            return None
        overrides = stage_vram_overrides or {}
        total = sum(overrides[s] if s in overrides else _STAGE_VRAM_MB.get(s, 0) for s in stages)
        return total or None

    def run_benchmark(self, device_id=None):
        """Synthetic throughput check; worker guidance is a heuristic, not model timing."""
        import time

        dev_id = device_id or self.default_device_id()
        kind = self.device_kind(dev_id)

        # 1. CPU Python-loop throughput (not an AI inference benchmark).
        t0 = time.perf_counter()
        sum_val = 0
        for i in range(300000):
            sum_val += (i * 3) % 7
        t1 = time.perf_counter()
        cpu_time = max(0.001, t1 - t0)

        gpu_time = None
        vram_mb = None
        tflops = None

        # 2. PyTorch GPU Benchmark if CUDA / MPS is available
        if torch is not None and dev_id != "cpu":
            try:
                if dev_id.startswith("cuda:") and torch.cuda.is_available():
                    idx = int(dev_id.split(":")[1])
                    device = torch.device(f"cuda:{idx}")
                    vram_mb = torch.cuda.get_device_properties(idx).total_memory // (1024 * 1024)

                    x = torch.randn(2048, 2048, device=device, dtype=torch.float32)
                    torch.cuda.synchronize()
                    t_gpu0 = time.perf_counter()
                    for _ in range(5):
                        _ = torch.matmul(x, x)
                    torch.cuda.synchronize()
                    t_gpu1 = time.perf_counter()
                    gpu_time = max(0.0001, (t_gpu1 - t_gpu0) / 5.0)
                    tflops = round((2 * (2048 ** 3) / gpu_time) / 1e12, 2)
                    del x
                    torch.cuda.empty_cache()

                elif dev_id == "mps" and getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available():
                    device = torch.device("mps")
                    x = torch.randn(1024, 1024, device=device)
                    t_gpu0 = time.perf_counter()
                    for _ in range(5):
                        _ = torch.matmul(x, x)
                    t_gpu1 = time.perf_counter()
                    gpu_time = max(0.0001, (t_gpu1 - t_gpu0) / 5.0)
                    del x
            except Exception as e:
                print(f"[BENCHMARK] GPU bench notice: {e}")

        # 3. Compute Recommendations
        cores = self.cpu_cores
        if kind == "dedicated":
            recommended_workers = min(max(2, cores // 2), 6)
            score = round(tflops * 100, 1) if tflops else 85.0
        elif kind == "integrated":
            recommended_workers = min(max(1, cores // 4), 3)
            score = 50.0
        else:
            recommended_workers = min(max(1, cores // 2), 4)
            score = round(10.0 / cpu_time, 1)

        return {
            "device_id": dev_id,
            "kind": kind,
            "score": score,
            "cpu_time_sec": round(cpu_time, 4),
            "gpu_time_sec": round(gpu_time, 4) if gpu_time else None,
            "tflops": tflops,
            "vram_total_mb": vram_mb,
            "recommended_workers": recommended_workers,
            "recommended_precision": "float16" if kind == "dedicated" else "float32",
        }
