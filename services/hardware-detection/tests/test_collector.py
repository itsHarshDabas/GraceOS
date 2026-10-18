"""Collector tests: missing files/commands fill ``errors``, never crash."""

from __future__ import annotations

import json
import subprocess

import grace_hw.collector as collector
from grace_hw.collector import collect

from .conftest import FIXTURES


def test_collect_partial_failure_keeps_good_sources(
    monkeypatch,
) -> None:
    """A missing meminfo nulls memory but CPU still parses, plus an error."""
    monkeypatch.setattr(
        collector,
        "_run",
        lambda argv, timeout=10: (_ for _ in ()).throw(
            FileNotFoundError(f"No such file: {argv[0]}")
        ),
    )
    report = collect(
        cpuinfo_path=str(FIXTURES / "cpuinfo_i5_1135g7.txt"),
        meminfo_path=str(FIXTURES / "does-not-exist"),
    )
    assert report["cpu"]["logical_cpus"] == 4
    assert report["memory"] == {
        "total_bytes": None,
        "available_bytes": None,
        "swap_total_bytes": None,
    }
    assert report["gpus"] == []
    assert report["disks"] == []
    assert any("meminfo" in e for e in report["errors"])
    assert any("lspci" in e for e in report["errors"])
    assert any("lsblk" in e for e in report["errors"])



def test_collect_all_sources_ok_with_monkeypatched_run(
    monkeypatch,
) -> None:
    lspci_text = (FIXTURES / "lspci_hybrid_nvidia_intel.txt").read_text(
        encoding="utf-8"
    )
    lsblk_text = (FIXTURES / "lsblk_mixed.json").read_text(encoding="utf-8")
    seen: list[list[str]] = []

    def fake_run(argv: list[str], timeout: int = 10) -> str:
        seen.append(list(argv))
        if argv[0] == "lspci":
            return lspci_text
        if argv[0] == "lsblk":
            return lsblk_text
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(collector, "_run", fake_run)
    report = collect(
        cpuinfo_path=str(FIXTURES / "cpuinfo_i5_1135g7.txt"),
        meminfo_path=str(FIXTURES / "meminfo_16gb.txt"),
    )
    assert report["errors"] == []
    assert report["cpu"]["logical_cpus"] == 4
    assert report["memory"]["total_bytes"] == 16245100 * 1024
    assert [g["vendor"] for g in report["gpus"]] == ["intel", "nvidia"]
    assert [d["name"] for d in report["disks"]] == [
        "nvme0n1",
        "sda",
        "sdb",
        "sdc",
    ]
    # Subprocesses use list argv (no shell=True) plus a timeout kwarg.
    assert seen[0][0] == "lspci"


def test_collect_missing_everything_reports_errors(
    monkeypatch, tmp_path
) -> None:
    missing_cpu = tmp_path / "cpuinfo"
    missing_mem = tmp_path / "meminfo"

    def fake_run(argv: list[str], timeout: int = 10) -> str:
        raise FileNotFoundError(f"No such file: {argv[0]}")

    monkeypatch.setattr(collector, "_run", fake_run)
    report = collect(
        cpuinfo_path=str(missing_cpu), meminfo_path=str(missing_mem)
    )
    assert report["cpu"] == {
        "model": None,
        "logical_cpus": None,
        "physical_cores": None,
        "flags": [],
    }
    assert report["memory"] == {
        "total_bytes": None,
        "available_bytes": None,
        "swap_total_bytes": None,
    }
    assert report["gpus"] == []
    assert report["disks"] == []
    assert len(report["errors"]) == 4
    assert any("cpuinfo" in e for e in report["errors"])
    assert any("meminfo" in e for e in report["errors"])
    assert any("lspci" in e for e in report["errors"])
    assert any("lsblk" in e for e in report["errors"])


def test_collect_command_failure_and_bad_json_are_errors(
    monkeypatch,
) -> None:
    def fake_run(argv: list[str], timeout: int = 10) -> str:
        if argv[0] == "lspci":
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
        return "{oops"

    monkeypatch.setattr(collector, "_run", fake_run)
    report = collect(
        cpuinfo_path=str(FIXTURES / "cpuinfo_i5_1135g7.txt"),
        meminfo_path=str(FIXTURES / "meminfo_16gb.txt"),
    )
    # The good sources still parse; only the broken ones show up in errors.
    assert report["cpu"]["logical_cpus"] == 4
    assert report["gpus"] == []
    assert report["disks"] == []
    assert any("lspci" in e for e in report["errors"])
    assert any("lsblk" in e for e in report["errors"])
    json.dumps(report)  # the report must always stay JSON-serializable
