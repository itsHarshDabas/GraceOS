#!/usr/bin/env bash
# Build GraceOS's own packages (packages/*) into out/repo, a pacman repo named "graceos".
# Run as a normal user on Arch with base-devel, git and make installed (makepkg refuses root).
# The packages workflow runs this and publishes out/repo to the repo-x86_64 GitHub release.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -ne 0 ]] || { echo "run as a normal user (makepkg refuses root)"; exit 1; }

repo=$PWD/out/repo
rm -rf "$repo"; mkdir -p "$repo"
export CANDYLAND_COMMIT=$(cat iso/candyland.ref)

for dir in packages/*/; do
  # -d: runtime dependencies are only needed on the target, not to package these.
  (cd "$dir" && PKGDEST="$repo" makepkg -fd --cleanbuild --noconfirm)
done

repo-add -q "$repo/graceos.db.tar.gz" "$repo"/*.pkg.tar.zst
# repo-add makes graceos.db and graceos.files symlinks; release assets can't be links.
for f in graceos.db graceos.files; do cp --remove-destination "$(readlink -f "$repo/$f")" "$repo/$f"; done
ls -lh "$repo"
