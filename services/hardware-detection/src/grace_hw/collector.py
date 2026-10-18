"""Live collection: read files / run commands, then parse them.

All I/O lives here so :mod:`grace_hw.parsers` stays pure and testable on
any OS. Every source is optional: failures are appended to ``errors`` and
the corresponding fields fall back to ``None`` / empty lists instead of
raising. No root is required; subprocesses use a list ``argv`` (never
``shell=True``) with a timeout.
"""

from __future__ import annotations

import subprocess

from grace_hw.parsers import (
    parse_cpuinfo,
    parse_lsblk_json,
    parse_lspci,
    parse_meminfo,
)

CPUINFO_PATH = "/proc/cpuinfo"
MEMINFO_PATH = "/proc/meminfo"
LSPCI_ARGV = ["lspci", "-k", "-nn"]
LSBLK_ARGV = ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MODEL,ROTA,TRAN"]
COMMAND_TIMEOUT = 10


def _read_file(path: str) -> str:
    """Read a text file. Split out for easy monkeypatching in tests."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _run(argv: list[str], timeout: int = COMMAND_TIMEOUT) -> str:
    """Run a command and return its stdout. Split out for monkeypatching."""
    completed = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{' '.join(argv)} exited with code {completed.returncode}: "
            f"{(completed.stderr or '').strip()}"
        )
    return completed.stdout or ""


def _unknown_cpu() -> dict:
    return {
        "model": None,
        "logical_cpus": None,
        "physical_cores": None,
        "flags": [],
    }


def _unknown_memory() -> dict:
    return {
        "total_bytes": None,
        "available_bytes": None,
        "swap_total_bytes": None,
    }


def collect(
    cpuinfo_path: str = CPUINFO_PATH,
    meminfo_path: str = MEMINFO_PATH,
    lspci_argv: list[str] | None = None,
    lsblk_argv: list[str] | None = None,
    timeout: int = COMMAND_TIMEOUT,
) -> dict:
    """Collect the full hardware report.

    ``cpuinfo_path`` / ``meminfo_path`` and the two ``argv`` lists are
    injectable so tests can point at fixtures or force failures without
    touching the real system. Returns ``{"cpu", "memory", "gpus", "disks",
    "errors"}``.
    """
    lspci_argv = list(lspci_argv) if lspci_argv is not None else list(
        LSPCI_ARGV
    )
    lsblk_argv = list(lsblk_argv) if lsblk_argv is not None else list(
        LSBLK_ARGV
    )
    errors: list[str] = []

    try:
        cpu = parse_cpuinfo(_read_file(cpuinfo_path))
    except FileNotFoundError:
        errors.append(f"cpuinfo not found: {cpuinfo_path} is missing")
        cpu = _unknown_cpu()
    except OSError as exc:
        errors.append(f"cpuinfo unreadable: {cpuinfo_path}: {exc}")
        cpu = _unknown_cpu()
    except Exception as exc:  # never crash because one source broke
        errors.append(f"cpuinfo parse failed: {exc}")
        cpu = _unknown_cpu()

    try:
        memory = parse_meminfo(_read_file(meminfo_path))
    except FileNotFoundError:
        errors.append(f"meminfo not found: {meminfo_path} is missing")
        memory = _unknown_memory()
    except OSError as exc:
        errors.append(f"meminfo unreadable: {meminfo_path}: {exc}")
        memory = _unknown_memory()
    except Exception as exc:
        errors.append(f"meminfo parse failed: {exc}")
        memory = _unknown_memory()

    try:
        gpus = parse_lspci(_run(lspci_argv, timeout=timeout))
    except FileNotFoundError:
        name = lspci_argv[0] if lspci_argv else "lspci"
        errors.append(f"lspci not found: {name} is not installed")
        gpus = []
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        errors.append(f"lspci failed: {exc}")
        gpus = []
    except Exception as exc:
        errors.append(f"lspci parse failed: {exc}")
        gpus = []

    try:
        disks = parse_lsblk_json(_run(lsblk_argv, timeout=timeout))
    except FileNotFoundError:
        name = lsblk_argv[0] if lsblk_argv else "lsblk"
        errors.append(f"lsblk not found: {name} is not installed")
        disks = []
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        errors.append(f"lsblk failed: {exc}")
        disks = []
    except ValueError as exc:
        errors.append(f"lsblk parse failed: {exc}")
        disks = []
    except Exception as exc:
        errors.append(f"lsblk parse failed: {exc}")
        disks = []

    return {
        "cpu": cpu,
        "memory": memory,
        "gpus": gpus,
        "disks": disks,
        "errors": errors,
    }

