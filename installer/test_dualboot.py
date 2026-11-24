# python -m pytest installer/  (no root, no disks, no archinstall needed)
# The same code against a real (loop) disk and archinstall's partitioning: build/dualboot-disk-test.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import dualboot as db  # noqa: E402

MiB, GiB = db.MiB, db.GiB
ESP, MSR, BASIC, RECOVERY = db.ESP_TYPE, *db.WINDOWS_TYPES, "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"
RECOVERY = "de94bba4-06d1-4d40-a16a-bfd50179d6ac"
MSR = "e3c9e316-0b5c-4db8-817d-f92df00215ae"

# A 500 GB laptop SSD after shrinking C: in Windows: ESP, MSR, C:, 100 GiB free, recovery.
SFDISK = {"partitiontable": {"label": "gpt", "device": "/dev/nvme0n1", "unit": "sectors", "firstlba": 34,
                             "lastlba": 976773134, "sectorsize": 512, "partitions": [
    {"node": "/dev/nvme0n1p1", "start": 2048, "size": 204800, "type": ESP.upper()},
    {"node": "/dev/nvme0n1p2", "start": 206848, "size": 32768, "type": MSR.upper()},
    {"node": "/dev/nvme0n1p3", "start": 239616, "size": 765460480, "type": BASIC.upper()},
    {"node": "/dev/nvme0n1p4", "start": 975124480, "size": 1646592, "type": RECOVERY.upper()}]}}
LSBLK = {"blockdevices": [
    {"path": "/dev/nvme0n1", "type": "disk", "size": 500107862016, "model": "Laptop SSD", "ro": False, "mountpoints": [None],
     "children": [
         {"path": "/dev/nvme0n1p1", "type": "part", "size": 104857600, "fstype": "vfat", "parttype": ESP, "label": "SYSTEM", "mountpoints": [None]},
         {"path": "/dev/nvme0n1p2", "type": "part", "size": 16777216, "fstype": None, "parttype": MSR, "mountpoints": [None]},
         {"path": "/dev/nvme0n1p3", "type": "part", "size": 391915765760, "fstype": "BitLocker", "parttype": BASIC, "mountpoints": [None]},
         {"path": "/dev/nvme0n1p4", "type": "part", "size": 843055104, "fstype": "ntfs", "parttype": RECOVERY, "mountpoints": [None]}]},
    {"path": "/dev/sda", "type": "disk", "size": 32 * GiB, "model": "USB stick", "ro": False, "fstype": "iso9660", "mountpoints": [None],
     "children": [{"path": "/dev/sda1", "type": "part", "fstype": "iso9660", "mountpoints": ["/run/archiso/bootmnt"]}]},
    {"path": "/dev/sdb", "type": "disk", "size": 1000 * GiB, "model": "New HDD", "ro": False, "mountpoints": [None]},
    {"path": "/dev/sr0", "type": "rom", "size": 1, "mountpoints": [None]},
]}


def laptop() -> db.Scan:
    disks = db.parse_disks(LSBLK, {"/dev/nvme0n1": SFDISK})
    esp = db.Esp(part=disks[0].parts[0], loaders=["Boot", "Microsoft"], windows=True, free=70 * MiB, fallback=b"bootmgfw")
    return db.Scan(uefi=True, secure_boot=False, disks=disks, esps=[esp], boot_entries={"0000": "Windows Boot Manager"})


def test_free_regions_are_aligned_and_skip_tiny_gaps():
    regions = db.free_regions(SFDISK)
    assert len(regions) == 1
    start, end = regions[0]
    assert start % MiB == 0 and end % MiB == 0
    assert start == (239616 + 765460480) * 512
    assert end == 975124480 * 512
    assert 99 * GiB < end - start < 101 * GiB


def test_free_regions_on_mbr_disks():
    # sfdisk --json has no firstlba/lastlba for MBR ("dos") disks: the disk size bounds the free space.
    mbr = {"partitiontable": {"label": "dos", "sectorsize": 512,
                              "partitions": [{"node": "/dev/sdc1", "start": 2048, "size": 204800, "type": "7"}]}}
    assert db.free_regions(mbr, disk_size=200 * MiB) == [(101 * MiB, 200 * MiB)]
    full = {"partitiontable": {"label": "dos", "sectorsize": 512, "partitions": [
        {"node": f"/dev/sdc{i}", "start": 2048 + i * 20480, "size": 20480, "type": "83"} for i in range(1, 5)]}}
    assert db.free_regions(full, disk_size=1000 * MiB) == []  # no primary slot left for root


def test_parse_disks_skips_the_live_usb_and_cd():
    disks = db.parse_disks(LSBLK, {"/dev/nvme0n1": SFDISK})
    assert [d.path for d in disks] == ["/dev/nvme0n1", "/dev/sdb"]
    nvme, sdb = disks
    assert nvme.pttype == "gpt" and [p.path for p in nvme.parts][0] == "/dev/nvme0n1p1"
    assert nvme.parts[0].is_esp and nvme.parts[0].start == 1 * MiB
    assert sdb.parts == [] and sdb.free and sdb.free[0][1] - sdb.free[0][0] > 999 * GiB


def test_hibernation_header():
    assert db.is_hibernated(b"HIBR\0\0\0\0") and db.is_hibernated(b"hibr")
    assert not db.is_hibernated(b"wake") and not db.is_hibernated(b"\0\0\0\0") and not db.is_hibernated(b"")


def test_scan_summary_and_warnings():
    s = laptop()
    assert s.windows and [p.path for p in s.bitlocker] == ["/dev/nvme0n1p3"]
    assert any("Microsoft" in o for o in s.other_os)
    w = " ".join(db.warnings(s))
    assert "BitLocker" in w and "recovery key" in w and "Secure Boot is off" in w


def test_protected_partitions_cover_windows_and_the_esp():
    p = db.protected_partitions(laptop())
    assert set(p) == {"/dev/nvme0n1p1", "/dev/nvme0n1p2", "/dev/nvme0n1p3", "/dev/nvme0n1p4"}
    assert "EFI system partition" in p["/dev/nvme0n1p1"] and "BitLocker" in p["/dev/nvme0n1p3"]


def test_erase_threats():
    s = laptop()
    # archinstall's "best-effort default layout" on the Windows disk: everything on it
    wipe = db.erase_threats([("/dev/nvme0n1", True, [(None, "create"), (None, "create")])], s)
    assert len(wipe) == 4 and all("whole disk /dev/nvme0n1" in t for t in wipe)
    # reusing the ESP but marking it for formatting
    fmt = db.erase_threats([("/dev/nvme0n1", False, [("/dev/nvme0n1p1", "modify"), (None, "create")])], s)
    assert fmt == ["/dev/nvme0n1p1: EFI system partition (Boot, Microsoft) (would be formatted)"]
    # deleting C:
    assert "would be deleted" in db.erase_threats([("/dev/nvme0n1", False, [("/dev/nvme0n1p3", "delete")])], s)[0]
    # a blank second disk, and install-alongside: nothing at risk
    assert db.erase_threats([("/dev/sdb", True, [(None, "create")])], s) == []
    assert db.erase_threats([("/dev/nvme0n1", False, [("/dev/nvme0n1p1", "existing"), (None, "create")])], s) == []


def test_confirm_threats(monkeypatch):
    t = db.erase_threats([("/dev/nvme0n1", True, [(None, "create")])], laptop())
    assert db.threat_targets(t) == ["/dev/nvme0n1"]
    assert not db.confirm_threats(t, set(), interactive=False)
    assert db.confirm_threats(t, {"/dev/nvme0n1"}, interactive=False)
    assert db.confirm_threats([], set(), interactive=False)
    monkeypatch.setattr("builtins.input", lambda _p: "yes")
    assert not db.confirm_threats(t, set(), interactive=True)
    monkeypatch.setattr("builtins.input", lambda _p: "/dev/nvme0n1")
    assert db.confirm_threats(t, set(), interactive=True)


def test_alongside_config_keeps_everything_and_reuses_the_esp():
    s = laptop()
    disk = s.disks[0]
    region = db.regions_for_alongside(s)[0][1]
    cfg = db.alongside_config(disk, region, s.esps[0].part)
    assert cfg["bootloader_config"] == {"bootloader": "Grub", "uki": False, "removable": False}
    dc = cfg["disk_config"]
    assert dc["config_type"] == "manual_partitioning"
    (mod,) = dc["device_modifications"]
    assert mod["device"] == "/dev/nvme0n1" and mod["wipe"] is False
    efi, root = mod["partitions"]
    assert efi["status"] == "existing" and efi["dev_path"] == "/dev/nvme0n1p1" and efi["mountpoint"] == "/efi"
    assert efi["flags"] == ["boot", "esp"]
    assert efi["start"] == {"value": MiB, "unit": "B", "sector_size": {"value": 512, "unit": "B"}}
    assert root["status"] == "create" and root["mountpoint"] == "/" and root["fs_type"] == "ext4"
    assert root["start"]["value"] * MiB == region[0] and root["size"]["value"] * MiB == region[1] - region[0]
    # the plan protects everything it doesn't create
    plan = [(mod["device"], mod["wipe"], [(p["dev_path"], p["status"]) for p in mod["partitions"]])]
    assert db.erase_threats(plan, s) == []


def test_alongside_on_a_second_disk_still_boots_from_the_windows_esp():
    s = laptop()
    sdb = s.disks[1]
    cfg = db.alongside_disk_config(sdb, sdb.free[0], s.esps[0].part)
    assert [m["device"] for m in cfg["device_modifications"]] == ["/dev/nvme0n1", "/dev/sdb"]
    assert [p["status"] for p in cfg["device_modifications"][0]["partitions"]] == ["existing"]
    assert db.pick_esp(s, sdb) is s.esps[0]


def test_no_alongside_without_free_space_or_on_mbr():
    s = laptop()
    s.disks[0].free = [(0, 10 * GiB)]
    s.disks[1].pttype = "dos"
    assert db.regions_for_alongside(s) == []


def test_small_esp():
    s = laptop()
    assert db.esp_free_ok(s.esps[0])
    s.esps[0].free = 8 * MiB
    assert not db.esp_free_ok(s.esps[0])


def test_view_mismatch_catches_a_missing_partition_table():
    s = laptop()
    parts = [p.path for p in s.disks[0].parts]
    assert db.view_mismatches([("/dev/nvme0n1", False, "gpt", parts)], s) == []
    # what archinstall sees when lsblk has no PTTYPE: an empty fresh table (found on a loop disk)
    bad = db.view_mismatches([("/dev/nvme0n1", False, "msdos", [])], s)
    assert bad and "dos partition table with 0" in bad[0] and "gpt table with 4" in bad[0]
    assert db.view_mismatches([("/dev/nvme0n1", True, "msdos", [])], s) == []  # a wipe is the erase guard's job


@pytest.mark.parametrize("devices, pkgs, cmds", [
    ([("0x030000", "0x8086", "0x46a6")], ["vulkan-intel", "intel-media-driver"], 0),
    ([("0x030000", "0x1002", "0x73df")], ["vulkan-radeon"], 0),
    ([("0x030000", "0x10de", "0x2684")], ["nvidia-open", "nvidia-utils", "libva-nvidia-driver"], 1),  # RTX 4090
    ([("0x030000", "0x10de", "0x1f08")], ["nvidia-open", "nvidia-utils", "libva-nvidia-driver"], 1),  # RTX 2060
    ([("0x030000", "0x10de", "0x1b80")], ["vulkan-nouveau"], 0),  # GTX 1080 (Pascal)
    ([("0x030000", "0x8086", "0x9a49"), ("0x030200", "0x10de", "0x25a2")],  # hybrid laptop
     ["vulkan-intel", "intel-media-driver", "nvidia-open", "nvidia-utils", "libva-nvidia-driver"], 1),
    ([("0x020000", "0x8086", "0x15f3")], [], 0),  # a network card isn't a GPU
    ([("0x030000", "0x1234", "0x1111")], [], 0),  # QEMU's standard VGA
])
def test_gpu_choice(devices, pkgs, cmds):
    got, notes, commands = db.gpu_choice(devices)
    assert got == pkgs and len(commands) == cmds and len(notes) >= (1 if pkgs else 0)


def test_pci_display_devices(tmp_path):
    for name, vals in {"0000:00:02.0": ("0x030000", "0x8086", "0x46a6"), "0000:00:14.0": ("0x0c0330", "0x8086", "0x51ed")}.items():
        d = tmp_path / name
        d.mkdir()
        for f, v in zip(("class", "vendor", "device"), vals):
            (d / f).write_text(v + "\n")
    assert db.pci_display_devices(tmp_path) == [("0x030000", "0x8086", "0x46a6")]


ARCH_GRUB = '''GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_CMDLINE_LINUX=""
# Uncomment to enable booting from the recovery mode menu entries
GRUB_DISABLE_RECOVERY="true"
# Probing for other operating systems is disabled for security reasons. Read
# documentation on GRUB_DISABLE_OS_PROBER, if still want to enable this
# functionality install os-prober and uncomment to detect and include other
# operating systems.
#GRUB_DISABLE_OS_PROBER="false"
'''


def test_grub_defaults():
    out = db.grub_defaults(ARCH_GRUB, probe_others=True)
    assert 'GRUB_DISABLE_RECOVERY="false"' in out and 'GRUB_DISABLE_RECOVERY="true"' not in out
    assert '\nGRUB_DISABLE_OS_PROBER="false"\n' in out and "#GRUB_DISABLE_OS_PROBER" not in out
    assert 'GRUB_CMDLINE_LINUX_RECOVERY="nomodeset"' in out
    assert db.grub_defaults(out, probe_others=True) == out  # running it twice changes nothing
    assert "\nGRUB_DISABLE_OS_PROBER" not in db.grub_defaults(ARCH_GRUB, probe_others=False)


ENTRY = """# Created by: archinstall
# Created on: 2026-11-23_21-00-00
title	Arch Linux (linux)
linux	/vmlinuz-linux
initrd	/initramfs-linux.img
options root=PARTUUID=1234 zswap.enabled=0 rw rootfstype=ext4
"""


def test_safe_entry():
    out = db.safe_entry(ENTRY, "/initramfs-linux-fallback.img")
    assert "title\tGraceOS (linux), safe graphics" in out
    assert "initrd\t/initramfs-linux-fallback.img" in out
    assert out.splitlines()[-1].endswith("rootfstype=ext4 nomodeset")
    assert "initrd\t/initramfs-linux.img" in db.safe_entry(ENTRY, None)


def test_parse_boot_entries():
    out = ("BootCurrent: 0003\nBootOrder: 0001,0000\n"
           "Boot0000* Windows Boot Manager\tHD(1,GPT,...)/\\EFI\\Microsoft\\Boot\\bootmgfw.efi\n"
           "Boot0001* GRUB\tHD(1,GPT,...)/\\EFI\\GRUB\\grubx64.efi\nBoot0003* UEFI: USB stick  PciRoot(0x0)\n")
    assert db.parse_boot_entries(out) == {"0000": "Windows Boot Manager", "0001": "GRUB", "0003": "UEFI: USB stick"}


def post_install_setup(tmp_path, monkeypatch, new_entry: bool):
    s = laptop()
    target = tmp_path / "mnt"
    esp_dir = target / "efi"
    (esp_dir / "EFI/BOOT").mkdir(parents=True)
    (esp_dir / "EFI/BOOT/BOOTX64.EFI").write_bytes(b"grub replaced it")
    (esp_dir / "EFI/Microsoft/Boot").mkdir(parents=True)
    (esp_dir / "EFI/Microsoft/Boot/bootmgfw.efi").write_bytes(b"bootmgfw")
    monkeypatch.setattr(db, "mounts_under", lambda _t: {"/dev/nvme0n1p1": esp_dir})
    entries = "Boot0000* Windows Boot Manager\tx\n" + ("Boot0001* GRUB\tx\n" if new_entry else "")
    monkeypatch.setattr(db, "run", lambda *cmd, check=True: entries if cmd[0] == "efibootmgr" else "")
    return s, target, esp_dir


def test_fallback_loader_is_put_back(tmp_path, monkeypatch):
    s, target, esp_dir = post_install_setup(tmp_path, monkeypatch, new_entry=True)
    post = db.PostInstall(s)
    post.finish(target)
    assert (esp_dir / "EFI/BOOT/BOOTX64.EFI").read_bytes() == b"bootmgfw"
    assert any("put back" in m and "GRUB" in m for m in post.messages)


def test_fallback_loader_kept_when_the_firmware_has_no_entry(tmp_path, monkeypatch):
    s, target, esp_dir = post_install_setup(tmp_path, monkeypatch, new_entry=False)
    post = db.PostInstall(s)
    post.finish(target)
    assert (esp_dir / "EFI/BOOT/BOOTX64.EFI").read_bytes() == b"grub replaced it"  # else nothing boots GraceOS
    assert any("WARNING" in m for m in post.messages)


def test_grub_post_install(tmp_path, monkeypatch):
    s, target, esp_dir = post_install_setup(tmp_path, monkeypatch, new_entry=True)
    (target / "etc/default").mkdir(parents=True)
    (target / "etc/default/grub").write_text(ARCH_GRUB)
    (esp_dir / "grub").mkdir()
    (esp_dir / "grub/grub.cfg").write_text("old")
    calls = []

    def fake_chroot(t, *cmd):
        calls.append(cmd)
        if cmd[0] == "grub-mkconfig":
            (esp_dir / "grub/grub.cfg").write_text("### BEGIN /etc/grub.d/30_os-prober ###\n"
                                                   "menuentry 'Windows Boot Manager (on /dev/nvme0n1p1)' {\n}\n"
                                                   "### END /etc/grub.d/30_os-prober ###\n")
        return True

    monkeypatch.setattr(db, "chroot", fake_chroot)
    post = db.PostInstall(s)
    post.finish(target)
    assert ("pacman", "-S", "--needed", "--noconfirm", "os-prober") in calls
    assert ("grub-mkconfig", "-o", "/efi/grub/grub.cfg") in calls
    assert 'GRUB_DISABLE_OS_PROBER="false"' in (target / "etc/default/grub").read_text()
    unit = (target / "etc/systemd/system/graceos-grub-rescan.service").read_text()
    assert "ExecStart=/usr/bin/grub-mkconfig -o /efi/grub/grub.cfg" in unit
    assert (target / "etc/systemd/system/multi-user.target.wants/graceos-grub-rescan.service").is_symlink()
    assert any("Windows found" in m for m in post.messages)


def test_systemd_boot_post_install(tmp_path, monkeypatch):
    s = laptop()
    s.esps = []
    target = tmp_path / "mnt"
    entries = target / "boot/loader/entries"
    entries.mkdir(parents=True)
    (entries / "2026_linux.conf").write_text(ENTRY)
    (target / "boot/initramfs-linux-fallback.img").write_text("")
    (target / "boot/vmlinuz-linux").write_text("")
    monkeypatch.setattr(db, "mounts_under", lambda _t: {"/dev/vda1": target / "boot"})
    monkeypatch.setattr(db, "run", lambda *cmd, check=True: "")
    db.PostInstall(s).finish(target)
    assert "title\tGraceOS (linux)" in (entries / "2026_linux.conf").read_text()
    safe = (entries / "2026_linux-safe.conf").read_text()
    assert "safe graphics" in safe and "nomodeset" in safe and "fallback" in safe
    db.PostInstall(s).finish(target)  # again: no "-safe-safe" entry
    assert sorted(p.name for p in entries.iterdir()) == ["2026_linux-safe.conf", "2026_linux.conf"]


def test_choose_alongside(monkeypatch, capsys):
    s = laptop()
    answers = iter(["1", "1", "2", ""])  # alongside, first free space, local-time clock, Enter
    monkeypatch.setattr("builtins.input", lambda _p: next(answers))
    config, commands = db.choose(s)
    assert config["disk_config"]["device_modifications"][0]["partitions"][0]["mountpoint"] == "/efi"
    assert commands == [db.RTC_LOCAL_COMMAND]
    out = capsys.readouterr().out
    assert "BitLocker" in out and "RealTimeIsUniversal" in out


def test_choose_stops_on_hibernated_windows(monkeypatch):
    s = laptop()
    s.parts[3].hibernated = True
    monkeypatch.setattr("builtins.input", lambda _p: "")
    with pytest.raises(SystemExit):
        db.choose(s)


def test_choose_without_another_os_does_nothing():
    s = laptop()
    s.disks = [s.disks[1]]
    s.esps = []
    assert db.choose(s) == ({}, [])


def test_rtc_local_command_writes_adjtime(tmp_path):
    import subprocess
    cmd = db.RTC_LOCAL_COMMAND.replace("/etc/adjtime", str(tmp_path / "adjtime"))
    subprocess.run(["bash", "-c", cmd], check=True)
    assert (tmp_path / "adjtime").read_text().splitlines() == ["0.0 0 0.0", "0", "LOCAL"]


def test_fallback_not_written_to_a_new_esp(tmp_path, monkeypatch):
    s, target, esp_dir = post_install_setup(tmp_path, monkeypatch, new_entry=True)
    (esp_dir / "EFI/Microsoft/Boot/bootmgfw.efi").unlink()  # erased and recreated on purpose
    db.PostInstall(s).finish(target)
    assert (esp_dir / "EFI/BOOT/BOOTX64.EFI").read_bytes() == b"grub replaced it"
