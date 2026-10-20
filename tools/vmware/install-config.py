"""archinstall config for the VMware test VM (30 GB /dev/sda, UEFI), same shape as build/install-test.py."""
import json
import uuid


def size(unit, value):
    return {"sector_size": {"value": 512, "unit": "B"}, "unit": unit, "value": value}


def part(mountpoint, fs, start, length, flags=()):
    return {"obj_id": str(uuid.uuid4()), "status": "create", "type": "primary", "dev_path": None,
            "mountpoint": mountpoint, "fs_type": fs, "start": start, "size": length,
            "flags": list(flags), "mount_options": [], "btrfs": []}


config = {
    "disk_config": {"config_type": "default_layout", "device_modifications": [{
        "device": "/dev/sda", "wipe": True, "partitions": [
            part("/boot", "fat32", size("MiB", 1), size("MiB", 1024), ["boot", "esp"]),
            part("/", "ext4", size("MiB", 1025), size("GiB", 27)),
        ]}]},
    "bootloader_config": {"bootloader": "Systemd-boot", "uki": False, "removable": True},
    # throwaway account on a throwaway virtual disk
    "users": [{"username": "tester", "!password": "grace-test", "sudo": True}],
}
open("inst.json", "w").write(json.dumps(config))
print("ok")
