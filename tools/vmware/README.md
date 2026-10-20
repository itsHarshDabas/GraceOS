# VMware helpers (Windows host)

Kept from the local build and test setup before the builder VM was retired; CI (`build-iso`) builds the ISO now. Trigger a manual run (workflow_dispatch) to get the ISO as an artifact.

- `build-in-vm.sh`: builds the packages and the ISO inside an Arch live VM. It expects a scratch disk mounted at `/mnt/build` holding `gos.bundle` (`git bundle create gos.bundle main`) and a `pkgcache/` folder. Run it as root.
- `vnc.py PORT shot|type|keys|click ...`: a tiny RFB client for VMware's local VNC (`RemoteDisplay.vnc.enabled`, no password, 127.0.0.1 only). It takes screenshots and types on the console, for example to set a throwaway root password on a live ISO before using SSH.
- `install-config.py`: writes `inst.json` for an unattended install onto the test VM's `/dev/sda`: `graceinstall --full|--minimal --silent --skip-ntp --skip-wkd --config inst.json`. The user it creates is a throwaway test account.

Gotchas:
- In the live ISO, `/usr/local/bin/graceinstall` shadows `/usr/bin/graceinstall`.
- Once a disk is installed, set `bios.bootOrder = "cdrom,hdd"` in the .vmx to boot the ISO again.
