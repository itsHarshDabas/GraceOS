#!/usr/bin/env python3
"""End-to-end installer test, entirely inside QEMU (it never touches a real disk).

1. Boots the ISO (UEFI) with a blank virtual disk and the serial console enabled.
2. Logs in as root on the serial console and runs `graceinstall --silent` with a test config.
3. Boots the installed virtual disk, logs in as the test user on tty1 (QEMU sendkey) and
   saves a screenshot, which should show the Grace Candyland desktop.

usage: sudo build/install-test.py out/graceos-*.iso [workdir=/var/tmp/graceos-install-test]
Without /dev/kvm (TCG) this takes a long time: the install alone can run for over an hour.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

USER, PASSWORD = "tester", "grace-test"  # throwaway account inside a throwaway disk image
OVMF_CODE = "/usr/share/edk2/x64/OVMF_CODE.4m.fd"
OVMF_VARS = "/usr/share/edk2/x64/OVMF_VARS.4m.fd"


def size(unit, value):
    return {"sector_size": None, "unit": unit, "value": value}


def part(mountpoint, fs, start, length, flags=()):
    return {"obj_id": str(uuid.uuid4()), "status": "create", "type": "primary", "dev_path": None,
            "mountpoint": mountpoint, "fs_type": fs, "start": start, "size": length,
            "flags": list(flags), "mount_options": [], "btrfs": []}


CONFIG = {
    "disk_config": {"config_type": "default_layout", "device_modifications": [{
        "device": "/dev/vda", "wipe": True, "partitions": [
            part("/boot", "fat32", size("MiB", 1), size("MiB", 1024), ["boot", "esp"]),
            part("/", "ext4", size("MiB", 1025), size("Percent", 100)),
        ]}]},
    "bootloader_config": {"bootloader": "Systemd-boot", "uki": False, "removable": True},
    "users": [{"username": USER, "!password": PASSWORD, "sudo": True}],
}


class Serial:
    def __init__(self, path):
        for _ in range(60):
            try:
                self.s = socket.socket(socket.AF_UNIX)
                self.s.connect(path)
                break
            except OSError:
                time.sleep(1)
        self.s.settimeout(5)
        self.buf = ""

    def expect(self, pattern, timeout):
        """Wait for a regex in the console output; returns the match. Use patterns the typed
        command can't contain itself, since the console echoes what we type."""
        end = time.time() + timeout
        while time.time() < end:
            if m := re.search(pattern, self.buf):
                self.buf = self.buf[m.end():]
                return m
            try:
                data = self.s.recv(65536).decode(errors="replace")
                sys.stdout.write(data)
                sys.stdout.flush()
                self.buf += data
            except socket.timeout:
                pass
        raise TimeoutError(f"no {pattern!r} on the serial console within {timeout}s")

    def send(self, line):
        self.s.sendall(line.encode() + b"\r")


def monitor(path, *cmds):
    s = socket.socket(socket.AF_UNIX)
    s.connect(path)
    for c in cmds:
        s.sendall(c.encode() + b"\n")
        time.sleep(0.3)
    s.close()


def type_on_screen(mon, text):
    keys = {"-": "minus", "\n": "ret", " ": "spc"}
    monitor(mon, *[f"sendkey {keys.get(c, c)}" for c in text])


def qemu(work, *extra):
    vars_ = work / "vars.fd"
    if not vars_.exists():
        shutil.copy(OVMF_VARS, vars_)
    accel = ["-accel", "kvm"] if os.access("/dev/kvm", os.W_OK) else ["-accel", "tcg"]
    return subprocess.Popen(["qemu-system-x86_64", *accel, "-m", "4096", "-smp", "4",
                             "-drive", f"if=pflash,format=raw,readonly=on,file={OVMF_CODE}",
                             "-drive", f"if=pflash,format=raw,file={vars_}",
                             "-drive", f"file={work / 'disk.qcow2'},if=virtio,format=qcow2",
                             "-nic", "user,model=virtio-net-pci", "-vga", "std", "-display", "none",
                             "-monitor", f"unix:{work / 'mon'},server,nowait", *extra])


def main():
    iso = Path(sys.argv[1]).resolve()
    work = Path(sys.argv[2] if len(sys.argv) > 2 else "/var/tmp/graceos-install-test")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(work / "disk.qcow2"), "24G"], check=True)

    # Boot the ISO's kernel directly so we can add console=ttyS0 to its command line.
    mnt = Path(tempfile.mkdtemp())
    subprocess.run(["mount", "-o", "loop,ro", str(iso), str(mnt)], check=True)
    try:
        for f in ("vmlinuz-linux", "initramfs-linux.img"):
            shutil.copy(mnt / "arch/boot/x86_64" / f, work / f)
        options = next(l for l in (mnt / "loader/entries/01-archiso-linux.conf").read_text().splitlines() if l.startswith("options"))
    finally:
        subprocess.run(["umount", str(mnt)])
        mnt.rmdir()
    cmdline = options.split(None, 1)[1] + " console=ttyS0,115200"

    print("== phase 1: install", flush=True)
    vm = qemu(work, "-cdrom", str(iso), "-kernel", str(work / "vmlinuz-linux"), "-initrd", str(work / "initramfs-linux.img"),
              "-append", cmdline, "-serial", f"unix:{work / 'serial'},server,nowait")
    con = Serial(str(work / "serial"))
    con.expect("login:", 1800)
    con.send("root")
    time.sleep(3)
    con.send("echo __READY_$((40+2))__")
    con.expect("__READY_42__", 120)
    con.send(f"cat > /root/test.json <<'EOF'\n{json.dumps(CONFIG)}\nEOF")
    con.send("graceinstall --silent --skip-ntp --skip-wkd --config /root/test.json > /root/gi.log 2>&1; echo __GI_RC=$?__")
    rc = con.expect(r"__GI_RC=(\d+)__", 4 * 3600).group(1)
    con.send("tail -n 25 /root/gi.log; echo __TAIL_$((40+2))__")
    con.expect("__TAIL_42__", 120)
    con.send("poweroff")
    vm.wait(600)
    print(f"\n== graceinstall exit status: {rc}", flush=True)
    if rc != "0":
        sys.exit(1)

    print("== phase 2: boot the installed system and log in on tty1", flush=True)
    vm = qemu(work)
    time.sleep(int(os.environ.get("BOOT_WAIT", 420)))
    type_on_screen(str(work / "mon"), f"{USER}\n")
    time.sleep(5)
    type_on_screen(str(work / "mon"), f"{PASSWORD}\n")
    time.sleep(int(os.environ.get("DESKTOP_WAIT", 300)))
    shot = work / "installed-desktop.png"
    monitor(str(work / "mon"), f"screendump {shot} -f png", "quit")
    vm.wait(60)
    print(f"== screenshot: {shot}" if shot.exists() else "== no screenshot taken")


if __name__ == "__main__":
    main()
