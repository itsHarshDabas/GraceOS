#!/usr/bin/env python3
"""Dual-boot disk test on a loop device (needs root; never touches a real disk).

Builds a 60 GiB sparse image laid out like a Windows laptop after "Shrink Volume": EFI system
partition with the Windows Boot Manager and its fallback copy, Microsoft reserved, a hibernated
(Fast Startup) NTFS C: drive, ~29 GiB free, and a recovery partition at the end. Then it checks
installer/dualboot.py against it, with archinstall's real disk code:

1. the scan finds Windows, the hibernation, the ESP and its fallback loader, and the free space;
2. archinstall's "default layout" (wipe the disk) is stopped by the guard, and the disk is unchanged;
3. the install-alongside plan passes the guard; archinstall creates the root partition in the free
   space and formats it, and the Windows partitions are byte-for-byte unchanged.

usage: sudo build/dualboot-disk-test.py [image=/var/tmp/graceos-dualboot.img]
Needs: archinstall (Arch package, or PYTHONPATH to its source), sgdisk, mkfs.fat, mkfs.ntfs, ntfs-3g
or the ntfs3 kernel driver, mtools when the kernel has no vfat.
"""

import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "installer"))
import dualboot  # noqa: E402

GiB, MiB = 1024 ** 3, 1024 ** 2
FAKE_BOOTMGR = b"MZ GraceOS test stand-in for bootmgfw.efi, Microsoft Corporation"


def sh(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def kernel_has(fs):
    return any(line.split()[-1] == fs for line in Path("/proc/filesystems").read_text().splitlines())


def ensure_nodes(loop):
    """Without udev (containers) the partition device nodes don't appear by themselves."""
    name = Path(loop).name
    for part in sorted(Path(f"/sys/block/{name}").glob(f"{name}p*")):
        node = Path("/dev") / part.name
        try:
            if not node.exists():
                major, minor = (part / "dev").read_text().strip().split(":")
                sh("mknod", str(node), "b", major, minor)
        except (OSError, subprocess.CalledProcessError):
            pass  # the kernel is re-reading the table right now; the caller retries


def digest_ready(dev):
    for _ in range(100):  # udev may be re-reading the table: wait for the partition to come back
        if not Path(f"/sys/class/block/{Path(dev).name}").exists():
            subprocess.run(["partx", "-u", dev.rsplit("p", 1)[0]], capture_output=True)
        ensure_nodes(dev.rsplit("p", 1)[0])
        if Path(dev).exists():
            break
        import time
        time.sleep(0.1)


def digest(dev, limit=None):
    digest_ready(dev)
    h = hashlib.sha256()
    with open(dev, "rb") as f:
        size = f.seek(0, 2)
        spans = [(0, size)] if limit is None or size <= 2 * limit else [(0, limit), (size - limit, limit)]
        for start, length in spans:
            f.seek(start)
            while length > 0:
                chunk = f.read(min(length, 8 * MiB))
                if not chunk:
                    break
                h.update(chunk)
                length -= len(chunk)
    return h.hexdigest()


def ensure_udev():
    """lsblk (and so archinstall) only knows partition tables and filesystems through udev."""
    if subprocess.run(["pgrep", "-x", "systemd-udevd"], capture_output=True).returncode != 0:
        for udevd in ("/usr/lib/systemd/systemd-udevd", "/lib/systemd/systemd-udevd"):
            if Path(udevd).exists():
                subprocess.run([udevd, "--daemon"], check=True, capture_output=True)
                break


def settle(loop):
    subprocess.run(["udevadm", "trigger", "--subsystem-match=block"], check=False)
    subprocess.run(["udevadm", "settle", "-t", "30"], check=False)
    ensure_nodes(loop)


def build(image):
    subprocess.run(["truncate", "-s", "60G", image], check=True)
    loop = sh("losetup", "-fP", "--show", image).strip()
    sh("sgdisk", "-Z", loop)
    sh("sgdisk", "-n1:1M:+100M", "-t1:EF00", "-c1:EFI system partition", "-n2:0:+16M", "-t2:0C01",
       "-c2:Microsoft reserved partition", "-n3:0:+30G", "-t3:0700", "-c3:Basic data partition",
       "-n4:-700M:0", "-t4:2700", "-c4:Recovery", loop)
    sh("partx", "-u", loop)
    ensure_nodes(loop)
    p = lambda n: f"{loop}p{n}"  # noqa: E731
    sh("mkfs.fat", "-F32", "-n", "SYSTEM", p(1))
    sh("mkfs.ntfs", "-Q", "-L", "Windows", p(3))
    sh("mkfs.ntfs", "-Q", "-L", "Recovery", p(4))
    tmp = Path(sh("mktemp", "-d").strip())
    (tmp / "bootmgfw.efi").write_bytes(FAKE_BOOTMGR)
    if kernel_has("vfat"):
        mnt = tmp / "esp"; mnt.mkdir()
        sh("mount", p(1), str(mnt))
        for d in ("EFI/Microsoft/Boot", "EFI/Boot"):
            (mnt / d).mkdir(parents=True)
        (mnt / "EFI/Microsoft/Boot/bootmgfw.efi").write_bytes(FAKE_BOOTMGR)
        (mnt / "EFI/Boot/bootx64.efi").write_bytes(FAKE_BOOTMGR)
        sh("umount", str(mnt))
    else:
        sh("mmd", "-i", p(1), "::/EFI", "::/EFI/Microsoft", "::/EFI/Microsoft/Boot", "::/EFI/Boot")
        sh("mcopy", "-i", p(1), str(tmp / "bootmgfw.efi"), "::/EFI/Microsoft/Boot/bootmgfw.efi")
        sh("mcopy", "-i", p(1), str(tmp / "bootmgfw.efi"), "::/EFI/Boot/bootx64.efi")
    mnt = tmp / "c"; mnt.mkdir()
    if kernel_has("ntfs3"):
        sh("mount", "-t", "ntfs3", p(3), str(mnt))
    else:
        sh("ntfs-3g", p(3), str(mnt))
    (mnt / "Windows/System32").mkdir(parents=True)
    (mnt / "Windows/System32/ntoskrnl.exe").write_bytes(b"not really")
    (mnt / "hiberfil.sys").write_bytes(b"HIBR" + bytes(4092))   # what Fast Startup leaves behind
    sh("umount", str(mnt))
    settle(loop)
    return loop


def patch_for_container(loop):
    """Make the scan work without udev, vfat or ntfs3 (it is unchanged on the live ISO):
    lsblk reports a loop device as type "loop"; read the filesystems with mtools / ntfs-3g."""
    real_run = dualboot.run

    def run(*cmd, check=True):
        out = real_run(*cmd, check=check)
        if cmd[0] == "lsblk":
            data = json.loads(out)
            data["blockdevices"] = [dict(d, type="disk") for d in data["blockdevices"] if d["path"] == loop]
            return json.dumps(data)
        return out

    dualboot.run = run
    real_ro = dualboot.read_only
    from contextlib import contextmanager

    @contextmanager
    def read_only(part, fstype):
        if fstype == "vfat" and not kernel_has("vfat"):
            tmp = Path(sh("mktemp", "-d").strip())
            sh("mcopy", "-s", "-n", "-i", part.path, "::/EFI", str(tmp))
            yield tmp
        elif fstype == "ntfs3" and not kernel_has("ntfs3"):
            tmp = Path(sh("mktemp", "-d").strip())
            sh("ntfs-3g", "-o", "ro", part.path, str(tmp))
            try:
                yield tmp
            finally:
                sh("umount", str(tmp))
        else:
            with real_ro(part, fstype) as path:
                yield path

    dualboot.read_only = read_only


def archinstall_config(data):
    from archinstall.lib.models.device import DiskLayoutConfiguration
    return DiskLayoutConfiguration.parse_arg(data)


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}: {name}{(' (' + detail + ')') if detail and not ok else ''}", flush=True)
    if not ok:
        check.failed += 1


check.failed = 0


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "/var/tmp/graceos-dualboot.img"
    Path(image).unlink(missing_ok=True)
    ensure_udev()
    loop = build(image)
    try:
        patch_for_container(loop)
        windows_parts = [f"{loop}p{n}" for n in (1, 2, 3, 4)]
        before = {p: digest(p, 256 * MiB) for p in windows_parts}

        scan = dualboot.scan()
        disk = next(d for d in scan.disks if d.path == loop)
        esp = next((e for e in scan.esps if e.part.disk == loop), None)
        check("scan finds Windows", scan.windows)
        check("scan finds the hibernated C: drive", [p.path for p in scan.hibernated] == [f"{loop}p3"])
        check("scan finds the Windows ESP and keeps its fallback loader",
              esp is not None and esp.windows and esp.fallback == FAKE_BOOTMGR)
        check("scan finds the free space", any(28 * GiB < b - a < 30 * GiB for a, b in disk.free),
              str([(a, b) for a, b in disk.free]))
        check("hibernation warning is shown", any("hibernated" in w for w in dualboot.warnings(scan)))

        dualboot.install_guard(scan, allowed=set(), interactive=False)
        from archinstall.lib.disk.filesystem import FilesystemHandler

        wipe = archinstall_config({"config_type": "default_layout", "device_modifications": [{
            "device": loop, "wipe": True, "partitions": [
                {"obj_id": str(uuid.uuid4()), "status": "create", "type": "primary", "dev_path": None,
                 "mountpoint": "/", "fs_type": "ext4", "start": dualboot.size_json(1),
                 "size": dualboot.size_json(20 * 1024), "flags": [], "mount_options": [], "btrfs": []}]}]})
        try:
            FilesystemHandler(wipe).perform_filesystem_operations()
            stopped = False
        except SystemExit:
            stopped = True
        check("the guard stops archinstall from wiping the Windows disk", stopped)
        check("after the stopped wipe, every Windows partition is unchanged",
              all(digest(p, 256 * MiB) == h for p, h in before.items()))

        region = max(disk.free, key=lambda r: r[1] - r[0])
        plan = dualboot.alongside_config(disk, region, esp.part)
        alongside = archinstall_config(plan["disk_config"])
        from archinstall.lib.bootloader.utils import validate_bootloader_layout
        from archinstall.lib.models.bootloader import BootloaderConfiguration
        boot = BootloaderConfiguration.parse_arg(plan["bootloader_config"], False)
        check("archinstall accepts GRUB (not removable) for the alongside layout",
              validate_bootloader_layout(boot, alongside) is None and not boot.removable)
        efi = [p for m in alongside.device_modifications for p in m.partitions if p.is_efi()]
        check("the existing ESP is mounted at /efi and left as it is (not formatted)",
              len(efi) == 1 and str(efi[0].mountpoint) == "/efi" and not efi[0].is_create_or_modify()
              and str(efi[0].dev_path) == f"{loop}p1")
        check("install-alongside plan has no threats", not dualboot.erase_threats(dualboot.disk_plan(alongside), scan))
        # In a container the new partition's device node can lag behind parted's commit: wait for it
        # before archinstall's own commands use it (no effect where udev keeps up, as on the ISO).
        import archinstall.lib.disk.device_handler as dh
        real_cmd = dh.SysCommand

        def waiting_cmd(cmd, *a, **kw):
            for attempt in range(5):
                for word in str(cmd).split():
                    if word.startswith(loop + "p"):
                        digest_ready(word)
                try:
                    return real_cmd(cmd, *a, **kw)
                except Exception as err:  # the node vanished while udev re-read the table
                    if "No such file" not in str(err) or attempt == 4:
                        raise

        dh.SysCommand = waiting_cmd
        try:
            FilesystemHandler(alongside).perform_filesystem_operations()
        finally:
            dh.SysCommand = real_cmd
        settle(loop)
        table = json.loads(sh("sfdisk", "--json", loop))["partitiontable"]["partitions"]
        new = [p for p in table if p["node"] not in windows_parts]
        fs = sh("blkid", "-p", "-o", "value", "-s", "TYPE", new[0]["node"]).strip() if len(new) == 1 else ""
        check("archinstall created one new partition, ext4, inside the free space",
              len(new) == 1 and fs == "ext4" and region[0] <= new[0]["start"] * 512
              and (new[0]["start"] + new[0]["size"]) * 512 <= region[1], f"{new} {fs}")
        check("the Windows partitions are unchanged (same table entries)",
              all(any(p["node"] == w for p in table) for w in windows_parts))
        check("the Windows partitions are unchanged (same bytes)",
              all(digest(p, 256 * MiB) == h for p, h in before.items()))
    finally:
        if not os.environ.get("KEEP"):
            subprocess.run(["losetup", "-d", loop])
            Path(image).unlink(missing_ok=True)
    print("ALL CHECKS PASSED" if not check.failed else f"{check.failed} CHECK(S) FAILED")
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
