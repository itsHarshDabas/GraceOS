#!/usr/bin/env bash
# Fail if any package in the manifest is missing from the Arch sync databases (run on Arch after `pacman -Sy`).
# GraceOS's own packages (packages/*) are skipped; they come from the graceos repo.
set -euo pipefail
cd "$(dirname "$0")/.."
rc=0
while read -r p; do
  [[ -d packages/$p ]] && continue  # GraceOS's own, built by build-packages.sh
  pacman -Si "$p" >/dev/null 2>&1 || { echo "MISSING: $p"; rc=1; }
done < <(grep -v '^\s*#' iso/packages.x86_64 | grep .)
exit $rc
