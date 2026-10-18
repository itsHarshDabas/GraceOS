#!/usr/bin/env bash
# Check a built GraceOS ISO's contents: checksum, branding, symlinks and required tools.
# usage: sudo build/verify-iso.sh out/graceos-<date>-x86_64.iso   (root needed for loop mounts)
set -euo pipefail
cd "$(dirname "$0")/.."
iso=$(realpath "$1")
[[ $EUID -eq 0 ]] || { echo "run as root (loop mounts)"; exit 1; }

mnt=$(mktemp -d); sfs=$(mktemp -d)
cleanup() { umount "$sfs" 2>/dev/null || true; umount "$mnt" 2>/dev/null || true; rmdir "$sfs" "$mnt"; }
trap cleanup EXIT
mount -o loop,ro "$iso" "$mnt"
mount -o loop,ro "$mnt/arch/x86_64/airootfs.sfs" "$sfs"

fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails+1)); fi; }

check "sha256 matches" '[[ ! -f $iso.sha256 ]] || (cd "$(dirname "$iso")" && sha256sum -c --quiet "$(basename "$iso").sha256")'
check "volume label is GRACEOS_*" '[[ $(blkid -o value -s LABEL "$iso") == GRACEOS_* ]]'
check "UEFI boot entries say GraceOS" 'grep -q "^title *GraceOS" "$mnt"/loader/entries/01-archiso-linux.conf'
check "BIOS boot menu says GraceOS" 'grep -q "MENU LABEL GraceOS" "$mnt"/boot/syslinux/archiso_sys-linux.cfg'
check "no leftover Arch install-medium titles" '! grep -rqs "Arch Linux install medium" "$mnt/loader" "$mnt/boot/syslinux"'
check "hostname is graceos" '[[ $(cat "$sfs/etc/hostname") == graceos ]]'
check "GraceOS MOTD" 'grep -q GraceOS "$sfs/etc/motd"'

while IFS=$'\t' read -r path target; do
  [[ -z $path || $path == \#* ]] && continue
  rel=${path#airootfs/}
  check "symlink /$rel -> $target" '[[ -L "$sfs/$rel" && $(readlink "$sfs/$rel") == "$target" ]]'
done < iso/symlinks.txt

# -L as well as -e: absolute symlinks (e.g. npm) cannot resolve from a mounted image.
for b in git python node npm uv rg fd jq btop fastfetch tmux makepkg lspci sshd; do
  check "tool $b" '[[ -e $sfs/usr/bin/$b || -L $sfs/usr/bin/$b ]]'
done

for b in Hyprland qs foot nautilus nmcli wpctl grace-candyland grace-approve; do
  check "tool $b" '[[ -e $sfs/usr/bin/$b || -L $sfs/usr/bin/$b ]]'
done
check "Grace Candyland session entry" '[[ -f $sfs/usr/share/wayland-sessions/grace-candyland.desktop ]]'
check "Grace shell installed" '[[ -f $sfs/usr/share/grace-candyland/shell/shell.qml ]]'
check "grace-* commands are executable" '[[ -x $sfs/usr/bin/grace-candyland && -x $sfs/usr/bin/grace-approve && -x $sfs/usr/bin/grace-launch && -x $sfs/usr/bin/grace-settings ]]'
check "live user grace (uid 1000, wheel)" 'grep -q "^grace:x:1000:1000:" "$sfs/etc/passwd" && grep -q "^wheel:.*grace" "$sfs/etc/group"'
check "tty1 autologin is grace" 'grep -q -- "--autologin grace" "$sfs/etc/systemd/system/getty@tty1.service.d/autologin.conf"'
check "grace's login starts the desktop" 'grep -q grace-candyland "$sfs/home/grace/.bash_profile" && [[ $(stat -c %u "$sfs/home/grace/.bash_profile") == 1000 ]]'
check "sudoers drop-in is 0440 root" '[[ $(stat -c %a:%u "$sfs/etc/sudoers.d/10-grace-live") == 440:0 ]]'

(( fails == 0 )) && echo "ALL CHECKS PASSED" || { echo "$fails check(s) failed"; exit 1; }
