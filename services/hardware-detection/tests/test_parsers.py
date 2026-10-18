"""Parser tests run on saved Linux outputs; they pass on any OS."""

from __future__ import annotations

import pytest

from grace_hw.parsers import (
    parse_cpuinfo,
    parse_lsblk_json,
    parse_lspci,
    parse_meminfo,
)

from .conftest import fixture


def test_parse_cpuinfo_multicore() -> None:
    cpu = parse_cpuinfo(fixture("cpuinfo_i5_1135g7.txt"))
    assert cpu["model"] == "11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz"
    assert cpu["logical_cpus"] == 4
    assert cpu["physical_cores"] == 4
    assert cpu["flags"] == ["avx2", "fma", "f16c"]
    assert "avx512f" not in cpu["flags"]


def test_parse_cpuinfo_no_topology_fields_gives_null_cores() -> None:
    text = (
        "processor\t: 0\n"
        "model name\t: Fake CPU 9000\n"
        "flags\t\t: fpu avx2\n"
        "\n"
        "processor\t: 1\n"
        "model name\t: Fake CPU 9000\n"
        "flags\t\t: fpu avx2\n"
        "\n"
    )
    cpu = parse_cpuinfo(text)
    assert cpu["model"] == "Fake CPU 9000"
    assert cpu["logical_cpus"] == 2
    assert cpu["physical_cores"] is None
    assert cpu["flags"] == ["avx2"]


def test_parse_cpuinfo_empty_is_all_unknown() -> None:
    cpu = parse_cpuinfo("")
    assert cpu == {
        "model": None,
        "logical_cpus": 0,
        "physical_cores": None,
        "flags": [],
    }


def test_parse_meminfo_converts_kb_to_bytes() -> None:
    mem = parse_meminfo(fixture("meminfo_16gb.txt"))
    assert mem == {
        "total_bytes": 16245100 * 1024,
        "available_bytes": 12039876 * 1024,
        "swap_total_bytes": 2097148 * 1024,
    }


def test_parse_meminfo_missing_fields_are_null() -> None:
    mem = parse_meminfo("MemTotal:        8192 kB\n")
    assert mem == {
        "total_bytes": 8192 * 1024,
        "available_bytes": None,
        "swap_total_bytes": None,
    }


def test_parse_lspci_hybrid_nvidia_intel() -> None:
    gpus = parse_lspci(fixture("lspci_hybrid_nvidia_intel.txt"))
    assert len(gpus) == 2
    intel, nvidia = gpus[0], gpus[1]
    assert intel["vendor"] == "intel"
    assert intel["pci_id"] == "00:02.0"
    assert "[8086:9a49]" in intel["description"]
    assert intel["kernel_driver"] == "i915"
    assert intel["kernel_modules"] == ["i915"]
    assert nvidia["vendor"] == "nvidia"
    assert nvidia["pci_id"] == "01:00.0"
    assert "[10de:1f95]" in nvidia["description"]
    assert nvidia["kernel_driver"] == "nvidia"
    assert nvidia["kernel_modules"] == ["nvidia_drm", "nvidia"]


def test_parse_lspci_amd_and_skips_non_gpu() -> None:
    gpus = parse_lspci(fixture("lspci_amd_desktop.txt"))
    assert [g["vendor"] for g in gpus] == ["amd"]
    assert gpus[0]["pci_id"] == "0b:00.0"
    assert "[1002:73ff]" in gpus[0]["description"]
    assert gpus[0]["kernel_driver"] == "amdgpu"
    assert gpus[0]["kernel_modules"] == ["amdgpu"]


def test_parse_lspci_vmware_svga_is_other_with_no_driver() -> None:
    gpus = parse_lspci(fixture("lspci_vmware_svga.txt"))
    assert len(gpus) == 1
    (gpu,) = gpus
    assert gpu["vendor"] == "other"
    assert gpu["pci_id"] == "00:0f.0"
    assert "[15ad:0405]" in gpu["description"]
    assert "VMware SVGA II Adapter" in gpu["description"]
    assert gpu["kernel_driver"] is None
    assert gpu["kernel_modules"] is None


def test_parse_lspci_vendor_comes_from_id_not_name() -> None:
    text = (
        "00:02.0 VGA compatible controller [0300]: "
        "Totally Not Intel Corp Device [1234:5678] (rev 01)\n"
        "\tKernel driver in use: fakdrv\n"
        "\tKernel modules: fakdrv\n"
    )
    (gpu,) = parse_lspci(text)
    assert gpu["vendor"] == "other"


def test_parse_lsblk_mixed_keeps_disks_only() -> None:
    disks = parse_lsblk_json(fixture("lsblk_mixed.json"))
    assert [d["name"] for d in disks] == ["nvme0n1", "sda", "sdb", "sdc"]
    nvme, sata, usb, bare = disks
    assert nvme["size_bytes"] == 1000204886016
    assert nvme["model"] == "Samsung SSD 980 PRO 1TB"
    assert nvme["rotational"] is False
    assert nvme["transport"] == "nvme"
    assert sata["size_bytes"] == 500107862016
    assert sata["transport"] == "sata"
    assert usb["rotational"] is True
    assert usb["transport"] == "usb"
    # Missing/blank fields become null instead of guesses.
    assert bare["model"] is None
    assert bare["rotational"] is False
    assert bare["transport"] is None


def test_parse_lsblk_json_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_lsblk_json("not json")
    with pytest.raises(ValueError):
        parse_lsblk_json('{"nope": []}')
