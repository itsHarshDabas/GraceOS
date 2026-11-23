#!/usr/bin/env bash
# Turn packages/* into AUR packages in out/aur/<name>/ (PKGBUILD, .SRCINFO and its local files).
# The aur workflow runs this and pushes each one to aur.archlinux.org; run it yourself to check.
#   - Git sources are pinned to the commits in iso/*.ref and get a fixed pkgver (rN.sha7),
#     because only -git packages may compute pkgver on the AUR.
#   - toffeetwirl repackages a release build, so the AUR calls it toffeetwirl-bin.
#   - graceos-release (GraceOS's own name and autostart) and yay-bin (already on the AUR) stay out.
# AUR_MAINTAINER="Name <email>" sets the Maintainer line. .SRCINFO needs makepkg (Arch);
# without it, or with --no-srcinfo, only the PKGBUILDs are written.
set -euo pipefail
cd "$(dirname "$0")/.."

AUR_PACKAGES=(grace-candyland cherrycolallm cottoncandy cortex-council toffeetwirl grace-candyland-desktop)
declare -A AUR_NAME=([toffeetwirl]=toffeetwirl-bin)
declare -A COMMIT_VAR=([grace-candyland]=CANDYLAND_COMMIT [cherrycolallm]=CHERRYCOLALLM_COMMIT
                       [cottoncandy]=COTTONCANDY_COMMIT [cortex-council]=CORTEXCOUNCIL_COMMIT)
declare -A REF_FILE=([CANDYLAND_COMMIT]=iso/candyland.ref [CHERRYCOLALLM_COMMIT]=iso/cherrycolallm.ref
                     [COTTONCANDY_COMMIT]=iso/cottoncandy.ref [CORTEXCOUNCIL_COMMIT]=iso/cortexcouncil.ref)

srcinfo=1; [[ ${1:-} == --no-srcinfo ]] && srcinfo=0
command -v makepkg >/dev/null || srcinfo=0
out=$PWD/out/aur
rm -rf "$out"; mkdir -p "$out"
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

# rN.sha7 of a commit, the same version the GraceOS repo's pkgver() gives it.
git_version() {  # url commit
  local dir=$work/$(basename "$1" .git)
  [[ -d $dir ]] || git clone -q --bare --filter=tree:0 "$1" "$dir"
  printf 'r%s.%s' "$(git -C "$dir" rev-list --count "$2")" "$(git -C "$dir" rev-parse --short=7 "$2")"
}

for pkg in "${AUR_PACKAGES[@]}"; do
  name=${AUR_NAME[$pkg]:-$pkg}
  dest=$out/$name
  cp -r "packages/$pkg" "$dest"
  pb=$dest/PKGBUILD

  if var=${COMMIT_VAR[$pkg]:-}; [[ -n $var ]]; then
    commit=$(cat "${REF_FILE[$var]}")
    url=$(sed -n 's/^url=//p' "$pb")
    sed -i "s|\${$var:?[^}]*}|$commit|" "$pb"
    sed -i "s|^pkgver=.*|pkgver=$(git_version "$url.git" "$commit")|" "$pb"
    sed -i '/^pkgver() {$/,/^}$/d' "$pb"                    # the AUR wants a fixed version
    sed -i '/(build-packages.sh passes it in)/d' "$pb"
  fi

  if [[ $name != "$pkg" ]]; then                          # toffeetwirl -> toffeetwirl-bin
    sed -i "s|^pkgname=.*|pkgname=$name\nprovides=($pkg)\nconflicts=($pkg)|" "$pb"
  fi
  # Inside the AUR, depend on the AUR names.
  for p in "${!AUR_NAME[@]}"; do sed -i "/^depends=(/,/)/s/\b$p\b\([^-]\|$\)/${AUR_NAME[$p]}\1/" "$pb"; done

  if [[ -n ${AUR_MAINTAINER:-} ]]; then
    sed -i "1s|^# Maintainer: .*|# Maintainer: $AUR_MAINTAINER\n# Contributor: GraceOS <https://github.com/itsHarshDabas/GraceOS>|" "$pb"
  fi
  if ((srcinfo)); then (cd "$dest" && makepkg --printsrcinfo >.SRCINFO); fi
  echo "$name $(sed -n 's/^pkgver=//p' "$pb")-$(sed -n 's/^pkgrel=//p' "$pb")"
done
((srcinfo)) || echo "note: no .SRCINFO written (needs makepkg on Arch)" >&2
