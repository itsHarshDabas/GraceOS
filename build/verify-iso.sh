#!/usr/bin/env bash
# Check a built GraceOS ISO's contents: checksum, branding, symlinks and required tools.
# usage: sudo build/verify-iso.sh out/graceos-<date>-x86_64.iso   (root needed for loop mounts)
#        sudo build/verify-iso.sh out/graceos-net-<date>-x86_64.iso   (GraceOS Net: its own checks)
set -euo pipefail
cd "$(dirname "$0")/.."
iso=$(realpath "$1")
edition=full
[[ $(basename "$iso") == graceos-net-* ]] && edition=net
[[ $EUID -eq 0 ]] || { echo "run as root (loop mounts)"; exit 1; }

mnt=$(mktemp -d); sfs=$(mktemp -d)
cleanup() { umount "$sfs" 2>/dev/null || true; umount "$mnt" 2>/dev/null || true; rmdir "$sfs" "$mnt"; }
trap cleanup EXIT
mount -o loop,ro "$iso" "$mnt"
mount -o loop,ro "$mnt/arch/x86_64/airootfs.sfs" "$sfs"

fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails+1)); fi; }

check "sha256 matches" '[[ ! -f $iso.sha256 ]] || (cd "$(dirname "$iso")" && sha256sum -c --quiet "$(basename "$iso").sha256")'
# GitHub refuses release files of 2 GiB or more; under that, the release is one ISO download.
check "ISO under 2 GiB ($(( $(stat -c %s "$iso") / 1048576 )) MiB)" '(( $(stat -c %s "$iso") < 2147483648 ))'
check "volume label is GRACEOS_*" '[[ $(blkid -o value -s LABEL "$iso") == GRACEOS_* ]]'
check "UEFI boot entries say GraceOS" 'grep -q "^title *GraceOS" "$mnt"/loader/entries/01-archiso-linux.conf'
check "BIOS boot menu says GraceOS" 'grep -q "MENU LABEL GraceOS" "$mnt"/boot/syslinux/archiso_sys-linux.cfg'
check "no leftover Arch install-medium titles" '! grep -rqs "Arch Linux install medium" "$mnt/loader" "$mnt/boot/syslinux"'
check "hostname is graceos" '[[ $(cat "$sfs/etc/hostname") == graceos ]]'
check "os-release says GraceOS (ID_LIKE=arch)" 'grep -q "^NAME=\"GraceOS\"" "$sfs/usr/lib/os-release" && grep -q "^ID_LIKE=arch" "$sfs/usr/lib/os-release"'
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

# GraceOS Net: the base and the tools to get online are on the ISO; the desktop and apps are not.
net_checks() {
  local net=$sfs/usr/share/graceos-net db
  for b in nmcli nmtui curl pacman; do check "tool $b" '[[ -e $sfs/usr/bin/$b || -L $sfs/usr/bin/$b ]]'; done
  check "no desktop on the ISO (it downloads at first boot)" '[[ ! -e $sfs/usr/bin/Hyprland && ! -e $sfs/usr/bin/grace-candyland && ! -e $sfs/usr/bin/cottoncandy ]]'
  check "grace-net-setup is executable" '[[ -x $sfs/usr/local/bin/grace-net-setup ]]'
  check "tty1 login runs grace-net-setup before the desktop" '[[ -f $sfs/etc/profile.d/00-grace-net.sh ]] && grep -q grace-net-setup "$sfs/etc/profile.d/00-grace-net.sh"'
  check "Net MOTD" 'grep -q "GraceOS Net" "$sfs/etc/motd"'
  check "boot entries say GraceOS Net and enlarge the live overlay" 'grep -q "^title *GraceOS Net" "$mnt"/loader/entries/01-archiso-linux.conf && grep -q "cow_spacesize=75%" "$mnt"/loader/entries/01-archiso-linux.conf "$mnt"/boot/syslinux/archiso_sys-linux.cfg'
  check "net.conf pins an Arch Linux Archive day" 'grep -Eq "^ARCH_ARCHIVE=https://archive.archlinux.org/repos/[0-9]{4}/[0-9]{2}/[0-9]{2}$" "$net/net.conf"'
  check "download pacman.conf uses that day and the pinned GraceOS repo" '(. "$net/net.conf"; grep -qF "Server = $ARCH_ARCHIVE/\$repo/os/\$arch" "$net/pacman.conf" && grep -qxF "Server = $GRACEOS_REPO_URL" "$net/pacman.conf") && ! grep -q "^Server = file://" "$net/pacman.conf"'
  for db in core extra graceos; do check "pinned $db database on the ISO" '[[ -s $net/sync/$db.db ]]'; done
  for p in grace-candyland cottoncandy toffeetwirl cherrycola cortex-council ollama; do
    check "downloads $p" 'grep -qx "$p" "$net/packages"'
  done
  # Every download resolves in the pinned databases (pacman -Sp only prints URLs; nothing is fetched).
  local tmp; tmp=$(mktemp -d)
  mkdir -p "$tmp/sync" "$tmp/local" && cp "$net"/sync/*.db "$tmp/sync/"
  check "every download resolves in the pinned databases" \
    'mapfile -t pk < <(grep -v "^\s*#" "$net/packages" | grep .) && pacman --config "$net/pacman.conf" --dbpath "$tmp" -Sp "${pk[@]}" > "$tmp/urls" && echo "     $(wc -l < "$tmp/urls") files to download"'
  rm -rf "$tmp"
}

full_checks() {
  for b in Hyprland qs candysole nautilus nmcli wpctl grace-candyland grace-approve cherrycola cortex-council cottoncandy twirl ollama yay grace-wine; do
    check "tool $b" '[[ -e $sfs/usr/bin/$b || -L $sfs/usr/bin/$b ]]'
  done
  check "Grace Candyland session entry" '[[ -f $sfs/usr/share/wayland-sessions/grace-candyland.desktop ]]'
  check "Grace shell installed" '[[ -f $sfs/usr/share/grace-candyland/shell/shell.qml ]]'
  check "grace-* commands are executable" '[[ -x $sfs/usr/bin/grace-candyland && -x $sfs/usr/bin/grace-approve && -x $sfs/usr/bin/grace-launch && -x $sfs/usr/bin/grace-settings ]]'
  check "GraceOS packages installed" '(for p in graceos-release grace-candyland cherrycola cortex-council cottoncandy toffeetwirl yay-bin; do ls -d "$sfs/var/lib/pacman/local/$p-"[0-9r]* >/dev/null 2>&1 || exit 1; done)'
  check "lock screen" '[[ -f $sfs/usr/share/grace-candyland/shell/modules/Lock.qml && -e $sfs/usr/bin/hypridle ]]'
  check "CottonCandy is the default browser" 'grep -qx "x-scheme-handler/https=org.graceos.CottonCandy.desktop" "$sfs/etc/xdg/mimeapps.list" && [[ -f $sfs/usr/share/applications/org.graceos.CottonCandy.desktop ]]'
  check "ToffeeTwirl IDE with Grace built in" '[[ -f $sfs/usr/share/applications/twirl.desktop && -f $sfs/opt/toffeetwirl/resources/app/extensions/grace/package.json ]] && grep -q "\"nameLong\": \"ToffeeTwirl IDE\"" "$sfs/opt/toffeetwirl/resources/app/product.json"'
  check "Cortex Council app entry and built UI" '[[ -f $sfs/usr/share/applications/org.graceos.CortexCouncil.desktop && -x $sfs/usr/bin/grace-cortex && -f $sfs/usr/lib/cortex-council/dist/web/index.html ]]'
}

if [[ $edition == net ]]; then net_checks; else full_checks; fi

# Both editions: the live user, the GraceOS base and graceinstall (which installs over the network either way).
check "live user grace (uid 1000, wheel)" 'grep -q "^grace:x:1000:1000:" "$sfs/etc/passwd" && grep -q "^wheel:.*grace" "$sfs/etc/group"'
check "tty1 autologin is grace" 'grep -q -- "--autologin grace" "$sfs/etc/systemd/system/getty@tty1.service.d/autologin.conf"'
check "tty1 login starts the desktop" 'grep -q grace-candyland "$sfs/etc/profile.d/grace-candyland.sh"'
check "graceinstall is executable" '[[ -x $sfs/usr/local/bin/graceinstall ]]'
check "graceinstall package list" '[[ $(grep -c . "$sfs/usr/share/graceinstall/packages") -gt 30 ]] && grep -qx grace-candyland "$sfs/usr/share/graceinstall/packages" && grep -q "\[minimal\]" "$sfs/usr/share/graceinstall/packages"'
# The hook put GraceOS's os-release in place; archiso then appends IMAGE_ID/IMAGE_VERSION, so compare the start.
check "os-release guard hook" '[[ -f $sfs/usr/share/libalpm/hooks/graceos-release.hook ]] && head -c "$(stat -c %s "$sfs/usr/lib/graceos/os-release")" "$sfs/usr/lib/os-release" | cmp -s - "$sfs/usr/lib/graceos/os-release"'
check "zram config" '[[ -f $sfs/usr/lib/systemd/zram-generator.conf ]]'
# Wine is optional since 2026-11-23: not on the ISO, installed afterwards with grace-wine.
check "Wine is not preinstalled" '[[ ! -e $sfs/usr/bin/wine ]] && ! grep -qx wine "$sfs/usr/share/graceinstall/packages"'
check "Windows app support entry" '[[ -f $sfs/usr/share/applications/org.graceos.GraceWine.desktop ]]'
check "GraceOS base packages installed" '(for p in graceos-release yay-bin; do ls -d "$sfs/var/lib/pacman/local/$p-"[0-9r]* >/dev/null 2>&1 || exit 1; done)'
check "sudoers drop-in is 0440 root" '[[ $(stat -c %a:%u "$sfs/etc/sudoers.d/10-grace-live") == 440:0 ]]'

(( fails == 0 )) && echo "ALL CHECKS PASSED" || { echo "$fails check(s) failed"; exit 1; }
