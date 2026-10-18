"""Pure parsers for the hardware sources used by ``grace-hw``.

Every function here takes already-read text and returns plain ``dict`` /
``list`` structures. They never touch the filesystem, never spawn
subprocesses, and use no platform-specific modules, so the unit tests can
feed them saved Linux command outputs and run on any OS (including
Windows).
"""

from __future__ import annotations

import json
import re

#: CPU flags of interest. These matter for later inference-backend selection
#: (e.g. AVX2 vs AVX-512 vs FMA code paths), so the report records which of
#: them the machine actually has instead of guessing.
CPU_FLAGS_OF_INTEREST = ("avx2", "avx512f", "fma", "f16c")

#: ``lspci`` device classes treated as GPUs, matched case-insensitively
#: against the class name with the trailing ``[0300]``-style class code
#: stripped off.
_GPU_CLASSES = frozenset(
    {"vga compatible controller", "3d controller", "display controller"}
)

#: PCI vendor ID (lowercase hex, as printed by ``lspci -nn``) mapped to the
#: canonical vendor name. Any other ID is reported as ``"other"``. The
#: lookup is by numeric ID, never by the human-readable device name.
_VENDOR_BY_PCI_ID = {
    "10de": "nvidia",
    "1002": "amd",
    "1022": "amd",  # AMD host bridges / some chipset parts
    "8086": "intel",
}

#: A top-level ``lspci`` device line, e.g.
#: ``01:00.0 3D controller [0302]: NVIDIA ... [10de:1f95] (rev a1)``.
#: An optional ``0000:`` PCI domain prefix is accepted and dropped so the
#: reported ``pci_id`` is always the domainless slot address.
_LSPCI_DEVICE_RE = re.compile(
    r"^(?:[0-9a-fA-F]{4}:)?"
    r"(?P<slot>[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9])"
    r"\s+(?P<rest>.*)$"
)

#: A ``[vvvv:dddd]`` PCI ID token, as printed by ``lspci -nn``.
_LSPCI_IDS_RE = re.compile(r"\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]")


def _blocks(text: str) -> list[dict[str, str]]:
    """Split ``/proc``-style ``key : value`` text into per-block dicts."""
    parsed: list[dict[str, str]] = []
    for chunk in re.split(r"\n[ \t]*\n", text.strip()):
        fields: dict[str, str] = {}
        for line in chunk.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            if key and key not in fields:
                fields[key] = value.strip()
        if fields:
            parsed.append(fields)
    return parsed


def parse_cpuinfo(text: str) -> dict:
    """Parse ``/proc/cpuinfo`` text.

    Returns ``{"model", "logical_cpus", "physical_cores", "flags"}`` where
    ``model`` is the first ``model name`` seen (or ``None``),
    ``logical_cpus`` is the number of ``processor`` entries,
    ``physical_cores`` is the number of unique
    ``("physical id", "core id")`` pairs (or ``None`` when those fields are
    absent), and ``flags`` lists the :data:`CPU_FLAGS_OF_INTEREST` present,
    in canonical order.
    """
    logical_cpus = len(re.findall(r"(?m)^processor\s*:", text))
    blocks = _blocks(text)

    model: str | None = None
    seen_flags: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for fields in blocks:
        if model is None and fields.get("model name"):
            model = fields["model name"]
        if "flags" in fields:
            seen_flags.update(fields["flags"].lower().split())
        if "physical id" in fields and "core id" in fields:
            pairs.add((fields["physical id"], fields["core id"]))

    return {
        "model": model,
        "logical_cpus": logical_cpus,
        "physical_cores": len(pairs) if pairs else None,
        "flags": [f for f in CPU_FLAGS_OF_INTEREST if f in seen_flags],
    }


def parse_meminfo(text: str) -> dict:
    """Parse ``/proc/meminfo`` text.

    Returns ``{"total_bytes", "available_bytes", "swap_total_bytes"}`` read
    from ``MemTotal``, ``MemAvailable`` and ``SwapTotal`` (kB values
    multiplied by 1024). Any field that is missing is ``None``.
    """
    values: dict[str, int | None] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        match = re.match(r"\s*(\d+)", rest)
        if not match:
            continue
        values[key.strip()] = int(match.group(1)) * 1024

    return {
        "total_bytes": values.get("MemTotal"),
        "available_bytes": values.get("MemAvailable"),
        "swap_total_bytes": values.get("SwapTotal"),
    }


def parse_lspci(text: str) -> list[dict]:
    """Parse ``lspci -k -nn`` output, keeping GPU/display controllers only.

    Each entry is ``{"vendor", "pci_id", "description", "kernel_driver",
    "kernel_modules"}`` where ``vendor`` is one of ``nvidia`` / ``amd`` /
    ``intel`` / ``other`` (decided from the numeric PCI vendor ID, never
    the name), ``pci_id`` is the domainless slot address (``"01:00.0"``),
    ``description`` is the full device text after the class label (so the
    ``[vvvv:dddd]`` ID is preserved verbatim), ``kernel_driver`` is the
    ``Kernel driver in use`` value (or ``None``), and ``kernel_modules``
    is the list from the ``Kernel modules`` line (or ``None``).
    """
    gpus: list[dict] = []
    current: dict | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line[0] in (" ", "\t"):
            if current is None:
                continue
            detail = line.strip()
            label, _, value = detail.partition(":")
            label = label.strip().lower()
            if label == "kernel driver in use":
                current["kernel_driver"] = value.strip() or None
            elif label == "kernel modules":
                modules = [
                    m.strip()
                    for m in value.replace(",", " ").split()
                    if m.strip()
                ]
                current["kernel_modules"] = modules
            continue

        current = None
        match = _LSPCI_DEVICE_RE.match(line)
        if not match or ":" not in match.group("rest"):
            continue
        class_part, _, description = match.group("rest").partition(":")
        class_name = class_part.split("[")[0].strip().lower()
        if class_name not in _GPU_CLASSES:
            continue
        ids = _LSPCI_IDS_RE.findall(description)
        vendor_id = ids[0][0].lower() if ids else None
        current = {
            "vendor": _VENDOR_BY_PCI_ID.get(vendor_id, "other")
            if vendor_id
            else "other",
            "pci_id": match.group("slot"),
            "description": description.strip(),
            "kernel_driver": None,
            "kernel_modules": None,
        }
        gpus.append(current)

    return gpus


def _to_int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _to_str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text != "-" else None


def _to_bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "y"):
            return True
        if lowered in ("0", "false", "no", "n"):
            return False
    return None


def parse_lsblk_json(text: str) -> list[dict]:
    """Parse ``lsblk -J -b -o NAME,SIZE,TYPE,MODEL,ROTA,TRAN`` JSON output.

    Keeps entries whose ``type`` is exactly ``"disk"`` (loop, part, rom
    and friends are dropped) and returns ``{"name", "size_bytes", "model",
    "rotational", "transport"}`` per disk, with ``None`` for unknown
    values. Partition ``children`` are ignored.
    Raises :exc:`ValueError` on malformed JSON.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"lsblk output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(
        data.get("blockdevices"), list
    ):
        raise ValueError("lsblk JSON has no 'blockdevices' list")

    disks: list[dict] = []
    for device in data["blockdevices"]:
        if not isinstance(device, dict) or device.get("type") != "disk":
            continue
        disks.append(
            {
                "name": device.get("name"),
                "size_bytes": _to_int_or_none(device.get("size")),
                "model": _to_str_or_none(device.get("model")),
                "rotational": _to_bool_or_none(device.get("rota")),
                "transport": _to_str_or_none(device.get("tran")),
            }
        )
    return disks

