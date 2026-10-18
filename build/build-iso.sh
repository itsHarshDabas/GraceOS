#!/usr/bin/env bash
# Build the GraceOS ISO. Run as root on Arch Linux with the `archiso` package installed.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo "run as root (mkarchiso needs it)"; exit 1; }
command -v mkarchiso >/dev/null || { echo "install archiso: pacman -S archiso"; exit 1; }
command -v make >/dev/null || { echo "install make: pacman -S make"; exit 1; }

work=${WORK_DIR:-/var/tmp/graceos-work}
stage=$work/profile
# An interrupted mkarchiso can leave bind mounts behind; rm -rf would then reach the host.
grep -q " $work" /proc/mounts && { echo "mounts remain under $work; unmount first"; exit 1; }
rm -rf "$work"; mkdir -p "$stage" out
cp -a iso/. "$stage"/

# Windows checkouts flatten symlinks into text files; recreate every one listed in the manifest.
while IFS=$'\t' read -r path target; do
  [[ -z $path || $path == \#* ]] && continue
  ln -sfn "$target" "$stage/$path"
done < iso/symlinks.txt

# The desktop, Grace Candyland, lives in its own repo; install the commit pinned in iso/candyland.ref.
# CANDYLAND_SRC=/path/to/checkout installs a local copy instead (for working on both at once).
src=${CANDYLAND_SRC:-}
if [[ -z $src ]]; then
  src=$work/candyland
  git clone -q https://github.com/itsHarshDabas/grace-candyland "$src"
  git -C "$src" -c advice.detachedHead=false checkout -q "$(cat iso/candyland.ref)"
fi
make -s -C "$src" install DESTDIR="$stage/airootfs" PREFIX=/usr

mkarchiso -v -w "$work/mkarchiso" -o out "$stage"
iso=$(ls -t out/graceos-*.iso | head -1)
( cd out && sha256sum "$(basename "$iso")" > "$(basename "$iso").sha256" )
ls -lh out
