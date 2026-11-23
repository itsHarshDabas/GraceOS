#!/usr/bin/env bash
# Build a GraceOS ISO. Run as root on Arch Linux with the `archiso` package installed.
# usage: build-iso.sh [full|net]
#   full (default): everything on the ISO, works offline       -> out/graceos-<date>-x86_64.iso
#   net:  the base only; the desktop and apps download at first boot (docs/decisions/0009-graceos-net.md)
#                                                               -> out/graceos-net-<date>-x86_64.iso
# For net, NET_REPO_URL is where publish-iso.sh will put this build's GraceOS packages (out/net-repo).
# Without it the Net ISO downloads them from the rolling repo-x86_64 release instead, which is
# fine for trying a local build but stops working once that repo moves on.
set -euo pipefail
cd "$(dirname "$0")/.."
edition=${1:-full}
case $edition in
  full) iso_name=graceos ;;
  net) iso_name=graceos-net ;;
  *) echo "usage: $0 [full|net]"; exit 2 ;;
esac
[[ $EUID -eq 0 ]] || { echo "run as root (mkarchiso needs it)"; exit 1; }
command -v mkarchiso >/dev/null || { echo "install archiso: pacman -S archiso"; exit 1; }

work=${WORK_DIR:-/var/tmp/graceos-work}
stage=$work/profile
# An interrupted mkarchiso can leave bind mounts behind; rm -rf would then reach the host.
grep -q " $work" /proc/mounts && { echo "mounts remain under $work; unmount first"; exit 1; }
rm -rf "$work"; mkdir -p "$stage" out
cp -a iso/. "$stage"/
rm -rf "$stage/net"  # the Net overlay; applied below for net builds only

# Windows checkouts flatten symlinks into text files; recreate every one listed in the manifest.
while IFS=$'\t' read -r path target; do
  [[ -z $path || $path == \#* ]] && continue
  ln -sfn "$target" "$stage/$path"
done < iso/symlinks.txt

# GraceOS Net: the same profile with the desktop and app sections of packages.x86_64 left out.
# The live system is built from one Arch Linux Archive day, and the ISO carries that day's package
# databases plus this build's graceos.db, so grace-net-setup downloads exactly those versions, and
# pacman checks every file against the sha256 in those databases.
net_profile() {
  local rolling archive snap back first d net repo_url latest
  rolling=$(sed -n 's|^Server = \(.*/releases/download/repo-x86_64\)$|\1|p' iso/pacman.conf | head -1)
  if [[ -n ${ARCH_SNAPSHOT:-} ]]; then
    snap=$ARCH_SNAPSHOT
  else
    # Yesterday's (UTC) snapshot is complete; fall back a few days if it isn't up yet.
    for back in 1 2 3 4; do
      d=$(date -u -d "-$back day" +%Y/%m/%d)
      if curl -fsSI --retry 3 --max-time 60 "https://archive.archlinux.org/repos/$d/core/os/x86_64/core.db" >/dev/null; then
        snap=$d; break
      fi
    done
  fi
  [[ -n ${snap:-} ]] || { echo "no Arch Linux Archive snapshot reachable"; exit 1; }
  archive=https://archive.archlinux.org/repos/$snap
  echo "GraceOS Net: Arch packages from $archive"
  sed -i "s|^Include = /etc/pacman.d/mirrorlist\$|Server = $archive/\\\$repo/os/\\\$arch|" "$stage/pacman.conf"

  # Everything before the first non-[minimal] GraceOS section stays on the ISO, plus what it takes to
  # get online; the rest is downloaded.
  local -a on_iso=(networkmanager)
  first=$(grep -n '^# --- GraceOS' iso/packages.x86_64 | grep -v '\[minimal\]' | head -1 | cut -d: -f1)
  net=$stage/airootfs/usr/share/graceos-net
  mkdir -p "$net/sync"
  { head -n $((first - 1)) iso/packages.x86_64
    echo "# --- GraceOS Net: what it takes to get online (the desktop and apps download at first boot) ---"
    printf '%s\n' "${on_iso[@]}"; } > "$stage/packages.x86_64"
  tail -n +"$first" iso/packages.x86_64 | grep -vxF -f <(printf '%s\n' "${on_iso[@]}") > "$net/packages"

  for d in core extra; do
    curl -fsSL --retry 5 -o "$net/sync/$d.db" "$archive/$d/os/x86_64/$d.db"
  done
  if [[ -n ${NET_REPO_URL:-} ]]; then
    [[ -e out/repo/graceos.db ]] || { echo "NET_REPO_URL needs this build's packages in out/repo (build/build-packages.sh)"; exit 1; }
    repo_url=$NET_REPO_URL
    cp out/repo/graceos.db "$net/sync/"
    rm -rf out/net-repo; cp -a out/repo out/net-repo  # publish-iso.sh uploads these to NET_REPO_URL
  else
    repo_url=$rolling
    echo "WARNING: NET_REPO_URL unset; this Net ISO downloads GraceOS packages from the rolling $rolling"
    curl -fsSL --retry 5 -o "$net/sync/graceos.db" "$rolling/graceos.db"
  fi
  # The downloads use the build's pacman.conf (snapshot servers, NoExtract for docs and locales).
  sed "/^\[graceos\]/,/^Server/ s|^Server = .*|Server = $repo_url|" "$stage/pacman.conf" > "$net/pacman.conf"
  latest=${rolling%/releases/download/*}/releases/latest
  { printf 'ARCH_ARCHIVE=%q\n' "$archive"
    printf 'GRACEOS_REPO_URL=%q\n' "$repo_url"
    printf 'LATEST_URL=%q\n' "$latest"
    printf 'BUILT_FROM=%q\n' "$(git rev-parse --short HEAD 2>/dev/null || echo unknown), $(date -u +%Y-%m-%d)"; } > "$net/net.conf"

  cp -a iso/net/airootfs/. "$stage/airootfs/"
  sed -i -e 's/^iso_name=.*/iso_name="graceos-net"/' -e 's/^iso_application=.*/iso_application="GraceOS Net Live"/' \
    -e 's/^iso_label="GRACEOS_/iso_label="GRACEOS_NET_/' \
    -e 's|^\(  \["/usr/local/bin/graceinstall"\]="0:0:755"\)$|\1\n  ["/usr/local/bin/grace-net-setup"]="0:0:755"|' \
    "$stage/profiledef.sh"
  # The downloaded desktop lives in RAM: let the live overlay use 75% of it instead of archiso's 256 MiB.
  sed -i -e 's/GraceOS live medium/GraceOS Net live medium/g' \
    -e 's/archisosearchuuid=%ARCHISO_UUID%/& cow_spacesize=75%/' \
    "$stage"/efiboot/loader/entries/*.conf "$stage"/syslinux/*.cfg "$stage"/grub/*.cfg
}

# GraceOS's own packages come from the [graceos] repo in iso/pacman.conf (GitHub Releases).
# If build/build-packages.sh has built them into out/repo, use those instead.
if [[ -e out/repo/graceos.db ]]; then
  sed -i "s|^Server = .*/releases/download/repo-x86_64|Server = file://$PWD/out/repo|" "$stage/pacman.conf"
  echo "using the local GraceOS repo in out/repo"
fi

# graceinstall installs the same GraceOS package sets as this ISO (everything after the first GraceOS marker,
# with the section markers kept so it can tell the Minimal set apart).
install -Dm755 installer/graceinstall "$stage/airootfs/usr/local/bin/graceinstall"
mkdir -p "$stage/airootfs/usr/share/graceinstall"
sed -n '/^# --- GraceOS/,$p' iso/packages.x86_64 > "$stage/airootfs/usr/share/graceinstall/packages"

[[ $edition == net ]] && net_profile

mkarchiso -v -w "$work/mkarchiso" -o out "$stage"
iso=$(ls -t out/"$iso_name"-[0-9]*.iso | head -1)
( cd out && sha256sum "$(basename "$iso")" > "$(basename "$iso").sha256" )
ls -lh out

# Where the size goes: GitHub release files must stay under 2 GiB (verify-iso.sh checks it).
echo "== ISO size report"
du -h "$work/mkarchiso/iso/arch/x86_64/airootfs.sfs" "$work"/mkarchiso/iso/arch/boot/x86_64/* "$work"/mkarchiso/efiboot.img 2>/dev/null || true
echo "-- largest packages on the ISO (installed size, MiB)"
for d in "$work"/mkarchiso/x86_64/airootfs/var/lib/pacman/local/*/; do
  awk -v n="$(basename "$d")" '/^%SIZE%$/ { getline; printf "%8.1f  %s\n", $1 / 1048576, n }' "$d/desc"
done | sort -rn | sed -n 1,40p  # not head: it closes the pipe early, which pipefail counts as a failure
echo "-- shared data"
du -sh "$work"/mkarchiso/x86_64/airootfs/usr/share/{locale,man,doc,licenses} 2>/dev/null || true
