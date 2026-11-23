"""Dual-boot safety for graceinstall: keep Windows (or any other OS) intact on real hardware.

graceinstall imports this before it hands over to archinstall. It:
- scans the disks read-only: other operating systems, BitLocker, hibernated (Fast Startup) Windows,
  EFI system partitions (ESPs), free space, Secure Boot;
- offers "install alongside": GraceOS goes into free space, and the existing ESP is reused at /efi
  without formatting it (GRUB, so the kernels stay on the root partition and a 100 MiB Windows ESP is
  enough);
- guards archinstall's disk step: wiping a disk or formatting/deleting a partition that holds another
  OS or data needs the user to type the device name (`--allow-erase DEVICE` when unattended);
- after the install (archinstall's `on_genfstab` plugin hook, which runs with the new system still
  mounted): adds Windows to the GRUB menu with os-prober, adds a "safe graphics" boot entry, and puts
  back the ESP's fallback loader (EFI/BOOT/BOOTX64.EFI) if the bootloader install replaced it;
- picks GPU driver packages for the detected hardware.

Pure functions (no root, no disks) are at the top so the tests can cover them; the parts that touch
the system are below them.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

MiB = 1024 ** 2
GiB = 1024 ** 3
MIN_ROOT = 20 * GiB        # a Full install wrote 5.4 GB; leave room for models and updates
RECOMMENDED_ROOT = 40 * GiB
MIN_ESP_FREE = 32 * MiB    # GRUB's files on the ESP take about 10 MiB

ESP_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
WINDOWS_TYPES = {
    "e3c9e316-0b5c-4db8-817d-f92df00215ae": "Microsoft reserved",
    "de94bba4-06d1-4d40-a16a-bfd50179d6ac": "Windows recovery",
}
# Partitions with these filesystems hold something; never wipe or format them without asking.
DATA_FILESYSTEMS = {"ntfs", "BitLocker", "vfat", "exfat", "ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs",
                    "crypto_LUKS", "LVM2_member", "zfs_member", "apfs", "hfsplus", "jfs", "nilfs2",
                    "bcachefs", "swap", "linux_raid_member"}

SAFE_GRAPHICS = "nomodeset"
FALLBACK_REL = "EFI/BOOT/BOOTX64.EFI"
SECURE_BOOT_VAR = Path("/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c")
RTC_LOCAL_COMMAND = "printf '0.0 0 0.0\\n0\\nLOCAL\\n' > /etc/adjtime"
WINDOWS_UTC_COMMAND = ('reg add "HKLM\\System\\CurrentControlSet\\Control\\TimeZoneInformation"'
                       ' /v RealTimeIsUniversal /d 1 /t REG_DWORD /f')


# ---------------------------------------------------------------- data

@dataclass
class Part:
    path: str
    disk: str
    start: int            # bytes
    size: int             # bytes
    parttype: str = ""
    fstype: str = ""
    label: str = ""
    mountpoints: list[str] = field(default_factory=list)
    sector: int = 512
    # filled in by the scan
    windows: bool = False         # an NTFS partition with Windows on it
    hibernated: bool = False      # hiberfil.sys says Windows is hibernated (or Fast Startup)
    unreadable: str = ""          # why an NTFS partition couldn't be checked

    @property
    def is_esp(self) -> bool:
        return self.parttype.lower() == ESP_TYPE

    def describe(self) -> str:
        what = self.fstype or WINDOWS_TYPES.get(self.parttype.lower(), "") or "unknown"
        label = f' "{self.label}"' if self.label else ""
        return f"{self.path} {human(self.size)} {what}{label}"


@dataclass
class Disk:
    path: str
    size: int
    model: str = ""
    pttype: str = ""      # gpt, dos, or "" (no partition table)
    sector: int = 512
    parts: list[Part] = field(default_factory=list)
    free: list[tuple[int, int]] = field(default_factory=list)   # (start, end) in bytes, MiB-aligned


@dataclass
class Esp:
    part: Part
    loaders: list[str] = field(default_factory=list)   # directories under EFI/
    windows: bool = False
    free: int = 0
    fallback: bytes | None = None    # EFI/BOOT/BOOTX64.EFI before the install


@dataclass
class Scan:
    uefi: bool
    secure_boot: bool | None
    disks: list[Disk]
    esps: list[Esp]
    boot_entries: dict[str, str]     # efibootmgr Boot#### -> label, before the install

    @property
    def parts(self) -> list[Part]:
        return [p for d in self.disks for p in d.parts]

    @property
    def windows(self) -> bool:
        return any(e.windows for e in self.esps) or any(p.windows or p.fstype == "BitLocker" for p in self.parts)

    @property
    def bitlocker(self) -> list[Part]:
        return [p for p in self.parts if p.fstype == "BitLocker"]

    @property
    def hibernated(self) -> list[Part]:
        return [p for p in self.parts if p.hibernated]

    @property
    def other_os(self) -> list[str]:
        """Human-readable list of what else is installed."""
        found = []
        for e in self.esps:
            names = [n for n in e.loaders if n.lower() not in ("boot",)]
            if names:
                found.append(f"boot loaders on {e.part.path}: {', '.join(names)}")
        for p in self.parts:
            if p.windows:
                found.append(f"Windows on {p.path}")
            elif p.fstype == "BitLocker":
                found.append(f"a BitLocker-encrypted drive on {p.path} (most likely Windows)")
            elif p.fstype in ("apfs", "hfsplus"):
                found.append(f"macOS on {p.path}")
        return found


def human(n: int) -> str:
    return f"{n / GiB:.1f} GiB" if n >= GiB else f"{n / MiB:.0f} MiB"


# ---------------------------------------------------------------- pure helpers

def free_regions(table: dict, minimum: int = 16 * MiB) -> list[tuple[int, int]]:
    """Free (start, end) byte ranges of one disk from `sfdisk --json`, aligned inward to 1 MiB."""
    t = table["partitiontable"]
    ss = t.get("sectorsize", 512)
    first = t.get("firstlba", 2048) * ss
    last = (t.get("lastlba", 0) + 1) * ss       # exclusive
    taken = sorted((p["start"] * ss, (p["start"] + p["size"]) * ss) for p in t.get("partitions", []))
    regions, cursor = [], first
    for start, end in taken + [(last, last)]:
        if start > cursor:
            a = -(-cursor // MiB) * MiB
            b = start // MiB * MiB
            if b - a >= minimum:
                regions.append((a, b))
        cursor = max(cursor, end)
    return regions


def parse_disks(lsblk: dict, tables: dict[str, dict]) -> list[Disk]:
    """Disks from `lsblk -J -b -p -o ...` plus each disk's `sfdisk --json` (missing: no table).
    Skips the live medium (iso9660 or mounted under /run/archiso) and read-only devices."""
    disks = []
    for dev in lsblk.get("blockdevices", []):
        if dev.get("type") != "disk" or str(dev.get("ro")) in ("1", "True", "true"):
            continue
        children = dev.get("children") or []
        everything = [dev, *children]
        if any(c.get("fstype") == "iso9660" or any(str(m or "").startswith("/run/archiso") for m in c.get("mountpoints") or [])
               for c in everything):
            continue
        table = tables.get(dev["path"])
        t = table["partitiontable"] if table else {}
        geometry = {p["node"]: p for p in t.get("partitions", [])}
        ss = t.get("sectorsize", 512)
        disk = Disk(path=dev["path"], size=int(dev.get("size") or 0), model=(dev.get("model") or "").strip(),
                    pttype=t.get("label", ""), sector=ss)
        for c in children:
            if c.get("type") != "part":
                continue
            g = geometry.get(c["path"], {})
            disk.parts.append(Part(
                path=c["path"], disk=disk.path, start=g.get("start", 0) * ss, size=int(c.get("size") or 0),
                parttype=(c.get("parttype") or g.get("type") or "").lower(), fstype=c.get("fstype") or "",
                label=c.get("label") or c.get("partlabel") or "",
                mountpoints=[m for m in c.get("mountpoints") or [] if m], sector=ss))
        if table:
            disk.free = free_regions(table)
        elif not children:
            disk.free = [(MiB, disk.size // MiB * MiB - MiB)] if disk.size > 2 * MiB else []
        disks.append(disk)
    return disks


def is_hibernated(header: bytes) -> bool:
    """hiberfil.sys starts with "hibr" (or "HIBR") while Windows is hibernated, which includes
    Fast Startup's shutdown; ntfs-3g uses the same check before it mounts read-write."""
    return header[:4].lower() == b"hibr"


def protected_partitions(scan: Scan) -> dict[str, str]:
    """Every partition that holds an OS or data, with the reason, so the guard can name it."""
    out = {}
    for p in scan.parts:
        if p.windows:
            out[p.path] = "Windows"
        elif p.fstype == "BitLocker":
            out[p.path] = "BitLocker-encrypted (Windows)"
        elif p.is_esp:
            esp = next((e for e in scan.esps if e.part.path == p.path), None)
            loaders = ", ".join(esp.loaders) if esp and esp.loaders else "no loaders found"
            out[p.path] = f"EFI system partition ({loaders})"
        elif p.parttype in WINDOWS_TYPES:
            out[p.path] = WINDOWS_TYPES[p.parttype]
        elif p.fstype in DATA_FILESYSTEMS:
            out[p.path] = f"{p.fstype} data"
    return out


def erase_threats(plan: list[tuple[str, bool, list[tuple[str | None, str]]]], scan: Scan) -> list[str]:
    """What a disk plan would destroy. plan: [(disk, wipe, [(partition path, status)])], with
    archinstall's statuses: existing, modify (reformat), delete, create."""
    protected = protected_partitions(scan)
    threats = []
    for disk, wipe, parts in plan:
        if wipe:
            threats += [f"{path}: {why} (the whole disk {disk} would be erased)"
                        for path, why in protected.items() if any(p.path == path and p.disk == disk for p in scan.parts)]
        for path, status in parts:
            if path in protected and status in ("modify", "delete"):
                verb = "formatted" if status == "modify" else "deleted"
                threats.append(f"{path}: {protected[path]} (would be {verb})")
    return list(dict.fromkeys(threats))


def size_json(value: int, unit: str = "MiB", sector: int = 512) -> dict:
    return {"value": value, "unit": unit, "sector_size": {"value": sector, "unit": "B"}}


def alongside_disk_config(disk: Disk, region: tuple[int, int], esp: Part) -> dict:
    """archinstall disk_config: keep every existing partition, mount the existing ESP at /efi without
    formatting it, and create one ext4 root partition that fills the chosen free region."""
    start, end = region
    root = {"obj_id": str(uuid.uuid4()), "status": "create", "type": "primary", "dev_path": None,
            "mountpoint": "/", "fs_type": "ext4", "start": size_json(start // MiB, sector=disk.sector),
            "size": size_json((end - start) // MiB, sector=disk.sector), "flags": [], "mount_options": [], "btrfs": []}
    efi = {"obj_id": str(uuid.uuid4()), "status": "existing", "type": "primary", "dev_path": esp.path,
           "mountpoint": "/efi", "fs_type": "fat32", "start": size_json(esp.start, "B", esp.sector),
           "size": size_json(esp.size, "B", esp.sector), "flags": ["boot", "esp"],
           "mount_options": [], "btrfs": []}
    mods = []
    if esp.disk == disk.path:
        mods.append({"device": disk.path, "wipe": False, "partitions": [efi, root]})
    else:
        mods.append({"device": esp.disk, "wipe": False, "partitions": [efi]})
        mods.append({"device": disk.path, "wipe": False, "partitions": [root]})
    return {"config_type": "manual_partitioning", "device_modifications": mods}


def alongside_config(disk: Disk, region: tuple[int, int], esp: Part) -> dict:
    """The archinstall settings for install-alongside. GRUB, because systemd-boot needs the kernels on
    the ESP (Windows makes it 100 MiB) and GRUB reads them from the root partition. Not "removable":
    that would overwrite the ESP's fallback loader EFI/BOOT/BOOTX64.EFI, which belongs to Windows."""
    return {"disk_config": alongside_disk_config(disk, region, esp),
            "bootloader_config": {"bootloader": "Grub", "uki": False, "removable": False}}


def gpu_choice(devices: list[tuple[str, str, str]]) -> tuple[list[str], list[str], list[str]]:
    """(packages, notes, custom commands) for PCI display devices given as (class, vendor, device)
    hex strings from /sys/bus/pci/devices/*/. Package names are the ones archinstall's own
    graphics-driver menu installs (archinstall/lib/hardware.py, GfxPackage)."""
    pkgs, notes, cmds = [], [], []
    for cls, vendor, device in devices:
        if not cls.lower().startswith("0x03"):
            continue
        vendor = vendor.lower()
        dev = int(device, 16)
        if vendor == "0x8086":
            pkgs += ["vulkan-intel", "intel-media-driver"]
            notes.append("Intel graphics: vulkan-intel, intel-media-driver (video decoding)")
        elif vendor == "0x1002":
            pkgs += ["vulkan-radeon"]
            notes.append("AMD graphics: vulkan-radeon (OpenGL and video decoding come with mesa)")
        elif vendor == "0x10de":
            # nvidia-open supports Turing (GTX 16xx / RTX 20xx) and newer; their device IDs start at 0x1e00.
            if dev >= 0x1E00:
                pkgs += ["nvidia-open", "nvidia-utils", "libva-nvidia-driver"]
                notes.append("NVIDIA graphics (Turing or newer): nvidia-open, nvidia-utils, libva-nvidia-driver;"
                             " kernel mode setting turned on for Hyprland")
                cmds.append("mkdir -p /etc/modprobe.d && echo 'options nvidia_drm modeset=1 fbdev=1'"
                            " > /etc/modprobe.d/graceos-nvidia.conf")
            else:
                pkgs += ["vulkan-nouveau"]
                notes.append(f"NVIDIA graphics older than Turing (device {device}): the open nouveau driver."
                             " NVIDIA's current driver doesn't support this card; its legacy driver is AUR-only.")
    return list(dict.fromkeys(pkgs)), list(dict.fromkeys(notes)), list(dict.fromkeys(cmds))


def set_shell_var(text: str, key: str, value: str) -> str:
    """Set KEY=value in a shell-style config such as /etc/default/grub (uncommenting it if needed)."""
    line = f'{key}="{value}"'
    pattern = re.compile(rf"^#?\s*{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda _m: line, text, count=1)
    return text.rstrip("\n") + f"\n{line}\n"


def grub_defaults(text: str, probe_others: bool) -> str:
    """GraceOS's /etc/default/grub changes: a "recovery mode" entry per kernel that boots with basic
    graphics (nomodeset), and os-prober for the other operating systems."""
    text = set_shell_var(text, "GRUB_DISABLE_RECOVERY", "false")
    text = set_shell_var(text, "GRUB_CMDLINE_LINUX_RECOVERY", SAFE_GRAPHICS)
    if probe_others:
        text = set_shell_var(text, "GRUB_DISABLE_OS_PROBER", "false")
    return text


def safe_entry(entry: str, fallback_initrd: str | None) -> str:
    """A systemd-boot entry for basic graphics, made from archinstall's normal entry."""
    out = []
    for line in entry.splitlines():
        key = line.split(None, 1)[0] if line.strip() else ""
        if key == "title":
            line = re.sub(r"^title\s+.*?(\s*\(.*\))?$", lambda m: f"title\tGraceOS{m.group(1) or ''}, safe graphics", line)
        elif key == "initrd" and fallback_initrd and "initramfs" in line:
            line = f"initrd\t{fallback_initrd}"
        elif key == "options" and SAFE_GRAPHICS not in line.split():
            line = f"{line} {SAFE_GRAPHICS}"
        out.append(line)
    return "\n".join(out) + "\n"


def parse_boot_entries(efibootmgr_output: str) -> dict[str, str]:
    entries = {}
    for line in efibootmgr_output.splitlines():
        if m := re.match(r"^Boot([0-9A-Fa-f]{4})\*?\s+(.*?)(\t|\s{2,}|$)", line):
            entries[m.group(1).upper()] = m.group(2).strip()
    return entries


def esp_free_ok(esp: Esp) -> bool:
    return esp.free >= MIN_ESP_FREE


# ---------------------------------------------------------------- system access

def run(*cmd: str, check: bool = True) -> str:
    return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout


@contextmanager
def read_only(part: Part, fstype: str):
    """Mount a partition read-only (or use where it is already mounted)."""
    if part.mountpoints:
        yield Path(part.mountpoints[0])
        return
    tmp = tempfile.mkdtemp(prefix="graceinstall-scan-")
    try:
        subprocess.run(["mount", "-t", fstype, "-o", "ro", part.path, tmp], check=True, capture_output=True)
    except subprocess.CalledProcessError as err:
        os.rmdir(tmp)
        raise OSError((err.stderr or b"").decode(errors="replace").strip() or "mount failed") from None
    try:
        yield Path(tmp)
    finally:
        subprocess.run(["umount", tmp], check=False)
        os.rmdir(tmp)


def find_ci(base: Path, rel: str) -> Path | None:
    """Case-insensitive lookup (FAT and NTFS ignore case, the mount may not)."""
    cur = base
    for name in rel.split("/"):
        if not cur.is_dir():
            return None
        match = next((c for c in cur.iterdir() if c.name.lower() == name.lower()), None)
        if match is None:
            return None
        cur = match
    return cur


def inspect_esp(part: Part) -> Esp:
    esp = Esp(part=part)
    try:
        with read_only(part, "vfat") as root:
            efi = find_ci(root, "EFI")
            if efi:
                esp.loaders = sorted(c.name for c in efi.iterdir() if c.is_dir())
            esp.windows = find_ci(root, "EFI/Microsoft/Boot/bootmgfw.efi") is not None
            fb = find_ci(root, FALLBACK_REL)
            if fb and fb.is_file():
                esp.fallback = fb.read_bytes()
            st = os.statvfs(root)
            esp.free = st.f_bavail * st.f_frsize
    except OSError as err:
        part.unreadable = str(err)
    return esp


def inspect_ntfs(part: Part) -> None:
    try:
        with read_only(part, "ntfs3") as root:
            part.windows = find_ci(root, "Windows/System32") is not None
            hib = find_ci(root, "hiberfil.sys")
            if hib and hib.is_file():
                with open(hib, "rb") as f:
                    part.hibernated = is_hibernated(f.read(4))
    except OSError as err:
        # ntfs3 refuses some hibernated or damaged volumes even read-only
        part.unreadable = str(err)


def secure_boot_state() -> bool | None:
    try:
        return SECURE_BOOT_VAR.read_bytes()[4:5] == b"\x01"
    except OSError:
        return None


def scan() -> Scan:
    lsblk = json.loads(run("lsblk", "-J", "-b", "-p", "-o",
                           "NAME,PATH,TYPE,SIZE,FSTYPE,PARTTYPE,PARTLABEL,LABEL,MODEL,RO,MOUNTPOINTS"))
    tables = {}
    for dev in lsblk.get("blockdevices", []):
        if dev.get("type") == "disk":
            out = run("sfdisk", "--json", dev["path"], check=False)
            if out.strip():
                tables[dev["path"]] = json.loads(out)
    disks = parse_disks(lsblk, tables)
    esps = []
    for d in disks:
        for p in d.parts:
            if not p.fstype:  # lsblk reads udev's database; blkid probes the partition itself
                probe = dict(line.split("=", 1) for line in run("blkid", "-p", "-o", "export", p.path, check=False).splitlines()
                             if "=" in line)
                p.fstype, p.label = probe.get("TYPE", ""), p.label or probe.get("LABEL", "")
            if p.is_esp:
                esps.append(inspect_esp(p))
            elif p.fstype == "ntfs":
                inspect_ntfs(p)
    uefi = Path("/sys/firmware/efi").is_dir()
    entries = parse_boot_entries(run("efibootmgr", check=False)) if uefi else {}
    return Scan(uefi=uefi, secure_boot=secure_boot_state() if uefi else None, disks=disks, esps=esps,
                boot_entries=entries)


def pci_display_devices(root: Path = Path("/sys/bus/pci/devices")) -> list[tuple[str, str, str]]:
    out = []
    for dev in sorted(root.glob("*")):
        try:
            out.append(tuple((dev / f).read_text().strip() for f in ("class", "vendor", "device")))
        except OSError:
            continue
    return [d for d in out if d[0].lower().startswith("0x03")]


# ---------------------------------------------------------------- talking to the user

def warnings(s: Scan) -> list[str]:
    w = []
    for p in s.bitlocker:
        w.append(f"{p.path} is encrypted with BitLocker. Before you go on, have the recovery key at hand"
                 " (https://aka.ms/myrecoverykey) or suspend BitLocker in Windows: a new boot loader, a"
                 " changed boot order or Secure Boot settings make Windows ask for that key, and without"
                 " it the drive is lost.")
    for p in s.hibernated:
        w.append(f"Windows on {p.path} is hibernated, usually because of Fast Startup. Boot Windows, turn"
                 " off Fast Startup (Control Panel > Power Options > Choose what the power buttons do), or"
                 " run `powercfg /h off` as administrator, then shut down fully. Writing to a hibernated"
                 " Windows drive from Linux corrupts it, and Windows may undo GraceOS's boot changes on resume.")
    for p in s.parts:
        if p.fstype == "ntfs" and p.unreadable:
            w.append(f"Couldn't check {p.path} (NTFS) for hibernation: {p.unreadable}. If it is Windows, turn"
                     " off Fast Startup and shut down fully before installing.")
    if s.windows and s.secure_boot is False:
        w.append("Secure Boot is off. GraceOS boots without it. Windows 11 also starts with it off; if Windows"
                 " uses BitLocker it asks for the recovery key the first time after Secure Boot changed.")
    if s.windows and not s.uefi:
        w.append("This PC started the installer in legacy BIOS mode. Windows on modern PCs is installed in UEFI"
                 " mode, and a BIOS-mode GraceOS can't start it from its menu. Restart and pick the USB stick's"
                 " UEFI entry in the firmware boot menu.")
    return w


def report(s: Scan) -> None:
    print("\nDisks found:")
    for d in s.disks:
        print(f"  {d.path}  {human(d.size)}  {d.model}  ({d.pttype or 'no partition table'})")
        for p in d.parts:
            tag = " [Windows]" if p.windows else ""
            tag += " [hibernated]" if p.hibernated else ""
            print(f"    {p.describe()}{tag}")
        for a, b in d.free:
            if b - a >= GiB:
                print(f"    free space: {human(b - a)}")
    if s.other_os:
        print("\nAlready installed:\n  " + "\n  ".join(s.other_os))
    if w := warnings(s):
        print("\nBefore you install:")
        for line in w:
            print(f"  ! {line}")
    print()


def ask(prompt: str, default: str = "") -> str:
    try:
        return input(prompt).strip() or default
    except EOFError:
        return default


def regions_for_alongside(s: Scan) -> list[tuple[Disk, tuple[int, int]]]:
    return [(d, r) for d in s.disks if d.pttype == "gpt" for r in d.free if r[1] - r[0] >= MIN_ROOT]


def pick_esp(s: Scan, disk: Disk) -> Esp | None:
    usable = [e for e in s.esps if not e.part.unreadable]
    for pref in (lambda e: e.part.disk == disk.path and e.windows, lambda e: e.part.disk == disk.path,
                 lambda e: e.windows, lambda e: True):
        if m := [e for e in usable if pref(e)]:
            return m[0]
    return None


def choose(s: Scan) -> tuple[dict, list[str]]:
    """Interactive dual-boot choices. Returns (archinstall config to merge, custom commands)."""
    if not (s.other_os or s.windows):
        return {}, []
    report(s)
    if s.hibernated and ask("Windows is hibernated. Continue anyway? Not recommended. [y/N]: ").lower() != "y":
        sys.exit("graceinstall: shut Windows down fully (Fast Startup off), then run graceinstall again.")
    print("Another operating system is installed. How should GraceOS be installed?")
    regions = regions_for_alongside(s) if s.uefi else []
    print("  1) Alongside it, in free space (recommended). Nothing that exists is deleted or formatted.")
    print("  2) Partition it myself in the installer's Disk configuration menu (advanced).")
    print("  3) Quit.")
    if not regions:
        need = human(MIN_ROOT)
        print(f"\n  There is no free space of at least {need} on a GPT disk"
              + ("" if s.uefi else " (and this PC started in BIOS mode)") + ". To make room for option 1,"
              f" shrink Windows in Disk Management (right-click the C: drive > Shrink Volume, {human(RECOMMENDED_ROOT)}"
              " or more), shut down fully, and run graceinstall again.")
    choice = ask("Choose 1, 2 or 3 [1]: ", "1")
    config: dict = {}
    if choice == "3":
        sys.exit(0)
    if choice == "1":
        if not regions:
            sys.exit("graceinstall: no free space to install alongside; see above.")
        for i, (d, (a, b)) in enumerate(regions, 1):
            print(f"  {i}) {d.path} ({d.model or 'disk'}): {human(b - a)} free")
        n = ask(f"Install into which free space? [1-{len(regions)}, 1]: ", "1")
        disk, region = regions[int(n) - 1] if n.isdigit() and 1 <= int(n) <= len(regions) else regions[0]
        esp = pick_esp(s, disk)
        if esp is None:
            sys.exit("graceinstall: no readable EFI system partition found to boot from; use option 2.")
        if not esp_free_ok(esp):
            sys.exit(f"graceinstall: the EFI system partition {esp.part.path} has only {human(esp.free)} free;"
                     f" GRUB needs {human(MIN_ESP_FREE)}. Use option 2 and create a separate one.")
        config = alongside_config(disk, region, esp.part)
        print(f"\nGraceOS will use {human(region[1] - region[0])} of free space on {disk.path} (a new ext4"
              f" partition) and boot through the existing EFI partition {esp.part.path}, mounted at /efi and"
              " not formatted. The boot menu (GRUB) will list Windows. Review it all in the next menu.")
    else:
        print("\nIn Disk configuration, pick Manual partitioning, create / in free space, and give the existing"
              " EFI partition the mountpoint /efi *without* marking it for formatting; then choose GRUB as the"
              " bootloader (systemd-boot would need the kernels on that small partition). GraceOS stops and"
              " asks before anything that holds data is erased.")
    commands = []
    if s.windows:
        print("\nWindows keeps the PC's hardware clock in local time; Linux keeps it in UTC, so the clock is"
              " off by hours after switching. Pick one:")
        print("  1) UTC (recommended). Then, once, in Windows: open Command Prompt as administrator and run:")
        print(f"       {WINDOWS_UTC_COMMAND}")
        print("  2) Local time, like Windows. Works without touching Windows, but daylight saving changes can"
              " shift the clock if both systems adjust it.")
        if ask("Choose 1 or 2 [1]: ", "1") == "2":
            commands.append(RTC_LOCAL_COMMAND)
        print("Set your Timezone in the next menu either way (the default is UTC).")
    ask("\nPress Enter to open the installer menu.")
    return config, commands


# ---------------------------------------------------------------- the erase guard

def disk_plan(disk_config) -> list[tuple[str, bool, list[tuple[str | None, str]]]]:
    """archinstall's DiskLayoutConfiguration as plain data. Raises AttributeError if its shape changed."""
    plan = []
    for mod in disk_config.device_modifications:
        parts = [(str(p.dev_path) if p.dev_path else None, getattr(p.status, "value", str(p.status)))
                 for p in mod.partitions]
        plan.append((str(mod.device_path), bool(mod.wipe), parts))
    return plan


def disk_views(disk_config) -> list[tuple[str, bool, str, list[str]]]:
    """What archinstall believes is on each disk it will change: (disk, wipe, table type, partitions)."""
    views = []
    for mod in disk_config.device_modifications:
        disk = mod.device.disk
        views.append((str(mod.device_path), bool(mod.wipe), str(disk.type), [str(p.path) for p in disk.partitions]))
    return views


def view_mismatches(views: list[tuple[str, bool, str, list[str]]], scan: Scan) -> list[str]:
    """archinstall keeps a disk's existing partitions only if it read the partition table right. If
    lsblk had no table type (udev not ready), it starts from an empty table and the old partitions
    vanish; this compares its view with our own sfdisk reading and reports the difference."""
    out = []
    for path, wipe, table, parts in views:
        disk = next((d for d in scan.disks if d.path == path), None)
        if wipe or disk is None or not disk.parts:
            continue
        theirs = {"msdos": "dos"}.get(table, table)
        if theirs != disk.pttype or set(parts) != {p.path for p in disk.parts}:
            out.append(f"{path}: the installer read a {theirs or 'missing'} partition table with"
                       f" {len(parts)} partition(s), but the disk has a {disk.pttype} table with {len(disk.parts)}")
    return out


def threat_targets(threats: list[str]) -> list[str]:
    """The devices the user has to name to allow these threats: a disk for a wipe, else the partition."""
    out = []
    for t in threats:
        m = re.search(r"the whole disk (\S+)", t)
        out.append(m.group(1) if m else t.split(":", 1)[0])
    return sorted(set(out))


def confirm_threats(threats: list[str], allowed: set[str], interactive: bool) -> bool:
    if not threats:
        return True
    print("\n!!! The disk changes you chose would destroy:", file=sys.stderr)
    for t in threats:
        print(f"!!!   {t}", file=sys.stderr)
    targets = threat_targets(threats)
    if set(targets) <= allowed:
        print("!!! Allowed with --allow-erase.", file=sys.stderr)
        return True
    if not interactive:
        print("!!! Stopping. Pass --allow-erase DEVICE for each of: " + " ".join(targets), file=sys.stderr)
        return False
    answer = ask(f"Type {' '.join(targets)} to erase, or press Enter to stop and change nothing: ")
    return answer.split() == targets


def install_guard(s: Scan, allowed: set[str], interactive: bool) -> None:
    """Check archinstall's disk plan right before it touches the disks."""
    from archinstall.lib.disk.filesystem import FilesystemHandler

    original = FilesystemHandler.perform_filesystem_operations

    def guarded(self, *args, **kwargs):
        try:
            plan = disk_plan(self._disk_config)
        except AttributeError as err:
            # archinstall changed shape: refuse rather than guess, if anything is worth protecting
            if protected_partitions(s):
                sys.exit(f"graceinstall: can't check archinstall's disk plan ({err}); stopping to keep"
                         " the existing partitions safe.")
            return original(self, *args, **kwargs)
        try:
            mismatches = view_mismatches(disk_views(self._disk_config), s)
        except AttributeError as err:
            mismatches = [f"can't read archinstall's view of the disks ({err})"] if protected_partitions(s) else []
        if mismatches:
            sys.exit("graceinstall: stopping before any disk change, because the installer's view of the disks"
                     " is wrong and it could overwrite existing partitions:\n  " + "\n  ".join(mismatches)
                     + "\nWait a few seconds (or run `udevadm settle`) and run graceinstall again.")
        if not confirm_threats(erase_threats(plan, s), allowed, interactive):
            sys.exit("graceinstall: stopped; nothing on the disks was changed.")
        return original(self, *args, **kwargs)

    FilesystemHandler.perform_filesystem_operations = guarded


# ---------------------------------------------------------------- after the install

def mounts_under(target: Path) -> dict[str, Path]:
    out = {}
    for line in run("findmnt", "-rn", "-o", "SOURCE,TARGET", check=False).splitlines():
        src, _, mp = line.partition(" ")
        mp = mp.encode().decode("unicode_escape")
        if mp == str(target) or mp.startswith(str(target).rstrip("/") + "/"):
            out[src] = Path(mp)
    return out


def chroot(target: Path, *cmd: str) -> bool:
    r = subprocess.run(["arch-chroot", str(target), *cmd])
    return r.returncode == 0


class PostInstall:
    """archinstall plugin; on_genfstab runs at the very end, with the new system still mounted."""

    def __init__(self, s: Scan):
        self.scan = s
        self.messages: list[str] = []

    def on_genfstab(self, installation) -> None:
        try:
            self.finish(Path(installation.target))
        except Exception as err:  # never fail an otherwise finished install over these extras
            self.messages.append(f"GraceOS's dual-boot step failed: {err}")
        for m in self.messages:
            print(f"graceinstall: {m}")

    def finish(self, target: Path) -> None:
        mounts = mounts_under(target)
        boot_dirs = list(dict.fromkeys([target / "boot", *mounts.values()]))
        grub_cfg = next((d / "grub/grub.cfg" for d in boot_dirs if (d / "grub/grub.cfg").is_file()), None)
        entries = [d / "loader/entries" for d in boot_dirs if (d / "loader/entries").is_dir()]
        if grub_cfg and (target / "etc/default/grub").is_file():
            self.grub(target, grub_cfg)
        for e in entries:
            self.systemd_boot(e)
        self.restore_fallbacks(mounts)

    def grub(self, target: Path, cfg: Path) -> None:
        others = bool(self.scan.other_os or self.scan.windows)
        if others and not chroot(target, "pacman", "-S", "--needed", "--noconfirm", "os-prober"):
            self.messages.append("couldn't install os-prober; Windows may be missing from the GRUB menu"
                                 " (install os-prober, then run grub-mkconfig).")
        default = target / "etc/default/grub"
        default.write_text(grub_defaults(default.read_text(), others))
        inside = "/" + str(cfg.relative_to(target))
        chroot(target, "grub-mkconfig", "-o", inside)
        text = cfg.read_text(errors="replace")
        if others:
            found = "menuentry" in text.split("BEGIN /etc/grub.d/30_os-prober", 1)[-1].split("END /etc/grub.d/30_os-prober", 1)[0] \
                if "BEGIN /etc/grub.d/30_os-prober" in text else False
            # os-prober sometimes finds nothing inside a chroot: look again on the first boot
            flag = target / "var/lib/graceinstall/rescan-grub"
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.write_text("")
            unit = target / "etc/systemd/system/graceos-grub-rescan.service"
            unit.parent.mkdir(parents=True, exist_ok=True)
            unit.write_text("[Unit]\nDescription=GraceOS: add other operating systems to the GRUB menu (once)\n"
                            "ConditionPathExists=/var/lib/graceinstall/rescan-grub\n\n[Service]\nType=oneshot\n"
                            f"ExecStart=/usr/bin/grub-mkconfig -o {inside}\n"
                            "ExecStartPost=/usr/bin/rm -f /var/lib/graceinstall/rescan-grub\n\n"
                            "[Install]\nWantedBy=multi-user.target\n")
            wants = target / "etc/systemd/system/multi-user.target.wants"
            wants.mkdir(parents=True, exist_ok=True)
            link = wants / unit.name
            if not link.exists():
                link.symlink_to("/etc/systemd/system/graceos-grub-rescan.service")
            self.messages.append("GRUB menu: Windows " + ("found" if found else "not found yet; GRUB looks again on the first boot")
                                 + "; each kernel has a recovery entry with safe graphics (nomodeset).")
        else:
            self.messages.append("GRUB menu: each kernel has a recovery entry with safe graphics (nomodeset).")

    def systemd_boot(self, entries: Path) -> None:
        boot = entries.parent.parent
        for conf in sorted(entries.glob("*.conf")):
            text = conf.read_text()
            if "archinstall" not in text or conf.stem.endswith("-safe"):
                continue
            conf.write_text(re.sub(r"^title\s+Arch Linux", "title\tGraceOS", text, flags=re.MULTILINE))
            m = re.search(r"^initrd\s+/initramfs-(\S+)\.img", text, re.MULTILINE)
            fallback = f"/initramfs-{m.group(1)}-fallback.img" if m else None
            if fallback and not (boot / fallback.lstrip("/")).exists():
                fallback = None
            (entries / f"{conf.stem}-safe.conf").write_text(safe_entry(conf.read_text(), fallback))
        self.messages.append(f"systemd-boot: added a safe graphics (nomodeset) entry in {entries}.")
        if not any(boot.glob("vmlinuz-*")):
            self.messages.append(f"WARNING: systemd-boot's entries are in {boot}, but the kernels aren't there,"
                                 " so GraceOS won't start. With a reused Windows EFI partition, pick GRUB as the"
                                 " bootloader (install-alongside does).")

    def restore_fallbacks(self, mounts: dict[str, Path]) -> None:
        now = parse_boot_entries(run("efibootmgr", check=False)) if self.scan.uefi else {}
        new = {k: v for k, v in now.items() if k not in self.scan.boot_entries}
        for esp in self.scan.esps:
            if esp.fallback is None or esp.part.path not in mounts:
                continue
            path = find_ci(mounts[esp.part.path], FALLBACK_REL)
            if path is None or path.read_bytes() == esp.fallback:
                continue
            if esp.windows and find_ci(mounts[esp.part.path], "EFI/Microsoft/Boot/bootmgfw.efi") is None:
                continue  # a new ESP at the same path (the disk was erased on purpose): nothing to put back
            if not new:
                self.messages.append(
                    f"WARNING: the firmware didn't get a boot entry for GraceOS, so {esp.part.path}'s fallback"
                    f" loader {FALLBACK_REL} (previously {', '.join(esp.loaders) or 'another OS'}'s) now starts"
                    " GraceOS instead. Windows still starts from the GraceOS menu.")
                continue
            path.write_bytes(esp.fallback)
            self.messages.append(f"put back the original {FALLBACK_REL} on {esp.part.path};"
                                 f" GraceOS starts from its own firmware entry ({', '.join(new.values())}).")


def install_hooks(s: Scan, allowed: set[str], interactive: bool) -> None:
    from archinstall.lib.plugins import plugins

    install_guard(s, allowed, interactive)
    plugins["graceos-dualboot"] = PostInstall(s)
