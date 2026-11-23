#!/usr/bin/env bash
# Fail if any package in the manifest, or any dependency of packages/*, is missing from the Arch sync databases (run on Arch after `pacman -Sy`).
# GraceOS's own packages (packages/*) are skipped; they come from the graceos repo.
set -euo pipefail
cd "$(dirname "$0")/.."
rc=0
while read -r p; do
  [[ -d packages/$p ]] && continue  # GraceOS's own, built by build-packages.sh
  pacman -Si "$p" >/dev/null 2>&1 || { echo "MISSING: $p"; rc=1; }
done < <(grep -v '^\s*#' iso/packages.x86_64 | grep .)
# Every runtime dependency of GraceOS's own packages, too (grace-candyland-desktop lists a lot).
for pb in packages/*/PKGBUILD; do
  while read -r d; do
    d=${d%%[<>=]*}
    [[ -z $d || -d packages/$d ]] && continue
    pacman -Si "$d" >/dev/null 2>&1 || { echo "MISSING: $d (needed by ${pb%/PKGBUILD})"; rc=1; }
  done < <(CANDYLAND_COMMIT=- CHERRYCOLALLM_COMMIT=- COTTONCANDY_COMMIT=- CORTEXCOUNCIL_COMMIT=- \
           bash -c 'source "$1"; printf "%s\n" "${depends[@]}"' _ "$pb")
done
exit $rc
