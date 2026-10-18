#!/usr/bin/env bash
# Fail if any package in the manifest is missing from the sync databases (run on Arch after `pacman -Sy`).
set -euo pipefail
cd "$(dirname "$0")/.."
rc=0
while read -r p; do
  pacman -Si "$p" >/dev/null 2>&1 || { echo "MISSING: $p"; rc=1; }
done < <(grep -v '^\s*#' iso/packages.x86_64 | grep .)
exit $rc
