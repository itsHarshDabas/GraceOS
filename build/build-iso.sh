#!/usr/bin/env bash
# Build the GraceOS ISO. Run as root on Arch Linux with the `archiso` package installed.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo "run as root (mkarchiso needs it)"; exit 1; }
command -v mkarchiso >/dev/null || { echo "install archiso: pacman -S archiso"; exit 1; }

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

mkarchiso -v -w "$work/mkarchiso" -o out "$stage"
iso=$(ls -t out/graceos-*.iso | head -1)
( cd out && sha256sum "$(basename "$iso")" > "$(basename "$iso").sha256" )
ls -lh out
