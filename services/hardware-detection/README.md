# grace-hw — read-only hardware detection for GraceOS

`grace-hw` prints a JSON report describing the CPU, memory, GPUs and disks
of the machine it runs on. It is read-only: it parses `/proc` files and the
stdout of `lspci`/`lsblk`, never writes anything, and never needs root.

## Install and run

Requires Python 3.12+. From this directory:

```sh
uv run grace-hw
uv run grace-hw --pretty
uv run pytest -q
```

## Output schema

Top-level object with exactly five keys:

```json
{
  "cpu": {
    "model": "11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz",
    "logical_cpus": 4,
    "physical_cores": 4,
    "flags": ["avx2", "fma", "f16c"]
  },
  "memory": {
    "total_bytes": 16635018240,
    "available_bytes": 12328833024,
    "swap_total_bytes": 2147479552
  },
  "gpus": [
    {
      "vendor": "intel",
      "pci_id": "00:02.0",
      "description": "Intel Corporation TigerLake-LP GT2 [Iris Xe Graphics] [8086:9a49] (rev 01)",
      "kernel_driver": "i915",
      "kernel_modules": ["i915"]
    }
  ],
  "disks": [
    {
      "name": "nvme0n1",
      "size_bytes": 1000204886016,
      "model": "Samsung SSD 980 PRO 1TB",
      "rotational": false,
      "transport": "nvme"
    }
  ],
  "errors": []
}
```

Field rules:

- `cpu.model`: first `model name` from `/proc/cpuinfo`, or `null`.
- `cpu.logical_cpus`: count of `processor` entries (`null` if cpuinfo is
  missing). `cpu.physical_cores`: unique `physical id`/`core id` pairs, or
  `null` when those fields are absent (common in VMs/containers).
- `cpu.flags`: subset of `avx2`, `avx512f`, `fma`, `f16c` present in the
  cpuinfo flags, in that canonical order. Used later for inference-backend
  selection (e.g. AVX2 vs AVX-512 code paths).
- `memory.*_bytes`: `MemTotal`, `MemAvailable`, `SwapTotal` from
  `/proc/meminfo` (kB × 1024); `null` per missing field.
- `gpus[]`: entries from `lspci -k -nn` whose class is VGA compatible
  controller, 3D controller or Display controller. `vendor` is one of
  `nvidia`, `amd`, `intel`, `other`, decided from the numeric PCI vendor ID
  (`10de`, `1002`/`1022`, `8086`) — never from the device name.
  `pci_id` is the domainless slot (`01:00.0`). `kernel_driver` and
  `kernel_modules` come from the `Kernel driver in use` / `Kernel modules`
  lines, or `null` when absent.
- `disks[]`: entries from `lsblk -J -b -o NAME,SIZE,TYPE,MODEL,ROTA,TRAN`
  with `type == "disk"` only (loop/rom/part excluded). `rotational` is a
  bool, `transport` the `TRAN` value (`nvme`, `sata`, `usb`, …); unknown
  values are `null`.
- `errors[]`: one string per source that failed or was missing (for
  example `lspci not found: lspci is not installed`). Unknown values are
  `null`; the tool never guesses and never crashes because one source is
  missing.

## Data sources

| Report part | Source | Command / file |
|---|---|---|
| `cpu` | `/proc/cpuinfo` (`model name`, `processor`, `physical id`, `core id`, `flags`) | file read |
| `memory` | `/proc/meminfo` (`MemTotal`, `MemAvailable`, `SwapTotal`) | file read |
| `gpus` | `lspci -k -nn` (class filter, vendor ID, driver lines) | subprocess, 10 s timeout |
| `disks` | `lsblk -J -b -o NAME,SIZE,TYPE,MODEL,ROTA,TRAN` | subprocess, 10 s timeout |

Design: `grace_hw/parsers.py` holds pure functions
(`parse_cpuinfo`, `parse_meminfo`, `parse_lspci`, `parse_lsblk_json`) that
take text and return dicts — no filesystem or subprocess access, so tests
feed them saved outputs and pass on any OS. `grace_hw/collector.py` does
the live I/O with list `argv` (no `shell=True`), a timeout, and per-source
`try/except` that records into `errors`. `grace_hw/cli.py` prints the
report as JSON (`--pretty` for indented output).

## Limitations

- Linux only for live collection (`/proc`, `lspci`, `lsblk`). On other
  OSes the file/command sources fail and the report returns `null`s plus
  `errors` entries — by design, not a crash.
- No root required, and none is used.
- No vendor tools yet: GPU memory, temperature and utilisation (e.g. via
  `nvidia-smi`, `rocm-smi`, sysfs hwmon) are intentionally out of scope for
  T-007. `physical_cores` is `null` when the hypervisor hides the topology
  fields; the tool reports that instead of estimating.
- Whatever `lspci`/`lsblk` do not report (e.g. a GPU with no kernel driver
  line, a disk with a blank model) is `null`.

## Tests

```sh
uv run pytest -q
```

Pure-parser tests run against realistic saved outputs in
`tests/fixtures/`: a multi-core `cpuinfo`, a `meminfo`, hybrid
NVIDIA dGPU + Intel iGPU `lspci`, an AMD desktop `lspci`, a VMware SVGA
(no driver line) `lspci`, and mixed `lsblk` JSON (NVMe, SATA SSD, USB
disk, loop device excluded). Collector tests monkeypatch file reads and
the command runner to prove missing files/commands fill `errors` instead
of crashing. Tests never read real system files and pass on Windows.

## Verified on a real machine
Run on the Arch live builder VM (VMware, 4 vCPU, 8 GB): the CPU model, logical CPU count and flags (avx2, fma, f16c; no avx512f) match `/proc/cpuinfo` and `nproc`; the GPU (VMware SVGA II, `vmwgfx`) matches `lspci -nn`; memory and the 40 GB SATA disk match. The VM's 4 KB virtual floppy shows up as a disk, because that is how `lsblk` reports it.
