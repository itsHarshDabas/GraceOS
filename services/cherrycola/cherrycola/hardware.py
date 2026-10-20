"""What this PC can run: graphics cards, memory, and models that fit.

GPUs are read from sysfs (no lspci needed); NVIDIA memory comes from
nvidia-smi when the driver is installed.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import config as config_mod

# name, download size (GB), what it's for
CATALOG = [
    ("qwen3:0.6b", 0.5, "Tiny and quick, simple questions"),
    ("qwen3:1.7b", 1.4, "Small and fast"),
    ("qwen3:4b", 2.5, "Good everyday model"),
    ("gemma3:4b", 3.3, "Everyday model that also reads images"),
    ("qwen2.5-coder:7b", 4.7, "Writing and fixing code"),
    ("qwen3:8b", 5.2, "Stronger answers"),
    ("gemma3:12b", 8.1, "Strong, reads images"),
    ("qwen2.5-coder:14b", 9.0, "Stronger at code"),
    ("qwen3:14b", 9.3, "Strong answers"),
    ("gpt-oss:20b", 14.0, "OpenAI's open model"),
    ("qwen3:30b", 19.0, "Fast for its size (mixture of experts)"),
    ("qwen3:32b", 20.0, "Best quality here"),
]

_VENDORS = {"0x10de": "nvidia", "0x1002": "amd", "0x8086": "intel"}
_GB = 1024**3
_MIN_VRAM = 3 * _GB  # below this (APU carve-outs, old cards) run on the CPU
_DESKTOP_RAM = 2.5 * _GB  # left for the desktop and apps
_CPU_COMFORT_GB = 5.5  # bigger models answer too slowly on a CPU


@dataclass
class Gpu:
    vendor: str  # nvidia | amd | intel | other
    vram: int  # bytes, 0 when shared or unknown


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _nvidia_vram() -> int:
    if not shutil.which("nvidia-smi"):
        return 0
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout
        return int(out.split()[0]) * 1024**2  # MiB
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return 0


def detect_gpus(pci: Path = Path("/sys/bus/pci/devices")) -> list[Gpu]:
    gpus = []
    for dev in sorted(pci.iterdir()) if pci.is_dir() else []:
        if not _read(dev / "class").startswith("0x03"):  # display controller
            continue
        vendor = _VENDORS.get(_read(dev / "vendor"), "other")
        vram = _read(dev / "mem_info_vram_total")  # amdgpu
        if vendor == "nvidia":
            size = _nvidia_vram()
        else:
            size = int(vram) if vram.isdigit() else 0
        gpus.append(Gpu(vendor, size))
    return gpus


def package_installed(name: str) -> bool:
    if not shutil.which("pacman"):
        return False
    try:
        return subprocess.run(["pacman", "-Qq", name], capture_output=True,
                              timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def engine_package(gpus: list[Gpu]) -> tuple[str, str]:
    """The Ollama build for this PC and why."""
    if any(g.vendor == "nvidia" for g in gpus):
        return "ollama-cuda", "NVIDIA graphics (needs the NVIDIA driver)"
    big = [g for g in gpus if g.vram >= _MIN_VRAM]
    if big:
        name = "AMD" if big[0].vendor == "amd" else "Intel Arc" \
            if big[0].vendor == "intel" else "Your"
        return "ollama-vulkan", f"{name} graphics card, through Vulkan"
    return "ollama", "No graphics card with its own memory: runs on the CPU"


def recommend(ram: int | None, gpus: list[Gpu]) -> dict:
    """Models that fit, and the best everyday pick."""
    vram = max((g.vram for g in gpus), default=0)
    on_gpu = vram >= _MIN_VRAM or any(g.vendor == "nvidia" and g.vram
                                      for g in gpus)
    budget = vram if on_gpu else max(0, (ram or 0) - _DESKTOP_RAM)
    package, why = engine_package(gpus)
    models = []
    for name, size, note in CATALOG:
        fits = size * 1.2 * _GB <= budget
        slow = not on_gpu and size > _CPU_COMFORT_GB
        models.append({"model": name, "size_gb": size, "note": note,
                       "fits": fits, "slow": fits and slow})
    picks = [m for m in models if m["fits"] and not m["slow"]
             and "code" not in m["note"].lower()]
    best = picks[-1]["model"] if picks else \
        config_mod.default_model_for_ram(ram)
    return {
        "ram_gb": round((ram or 0) / _GB, 1),
        "vram_gb": round(vram / _GB, 1),
        "runs_on": "gpu" if on_gpu else "cpu",
        "engine": package,
        "engine_reason": why,
        "engine_installed": package_installed(package),
        "recommended": best,
        "models": models,
    }
