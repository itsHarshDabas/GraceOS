#!/usr/bin/env bash
# Build GraceOS's own packages (packages/*) into out/repo, a pacman repo named "graceos".
# Run as a normal user on Arch with base-devel, git and make installed (makepkg refuses root).
# The packages workflow runs this and publishes out/repo to the repo-x86_64 GitHub release.
# Every package and the database are signed (pacman checks them: SigLevel = Required). GPGKEY is the
# fingerprint of a secret key in your gpg (CI: build/import-signing-key.sh). It must be the key in
# packages/graceos-keyring, unless ALLOW_TEST_KEY=1, which builds graceos-keyring with GPGKEY instead
# (local and pull-request test builds; never publish those). docs/decisions/0014-signed-repo.md
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -ne 0 ]] || { echo "run as a normal user (makepkg refuses root)"; exit 1; }

[[ -n ${GPGKEY:-} ]] || { echo "set GPGKEY to the signing key's fingerprint (see the comment at the top)"; exit 1; }
gpg --batch --list-secret-keys "$GPGKEY" >/dev/null 2>&1 || { echo "no secret key $GPGKEY in your gpg"; exit 1; }
GPGKEY=$(gpg --batch --list-secret-keys --with-colons "$GPGKEY" | awk -F: '/^fpr/ { print $10; exit }')
export GPGKEY

repo=$PWD/out/repo
rm -rf "$repo"; mkdir -p "$repo"

# graceos-keyring holds the committed public key; a test key gets a keyring of its own in a copy.
keyring=packages/graceos-keyring
trusted=$(cut -d: -f1 "$keyring/graceos-trusted" 2>/dev/null || true)
if [[ $GPGKEY != "$trusted" ]]; then
  [[ ${ALLOW_TEST_KEY:-} == 1 ]] || {
    echo "GPGKEY $GPGKEY is not the GraceOS key in $keyring/graceos-trusted (${trusted:-none yet; run build/new-signing-key.sh})"; exit 1; }
  echo "WARNING: test build: graceos-keyring gets the test key $GPGKEY. Don't publish this repo."
  keyring=$(mktemp -d)/graceos-keyring
  cp -a packages/graceos-keyring "$keyring"
  gpg --batch --yes --export "$GPGKEY" > "$keyring/graceos.gpg"
  echo "$GPGKEY:4:" > "$keyring/graceos-trusted"
fi
export CANDYLAND_COMMIT=$(cat iso/candyland.ref)
export CHERRYCOLALLM_COMMIT=$(cat iso/cherrycolallm.ref)
export COTTONCANDY_COMMIT=$(cat iso/cottoncandy.ref)
export CORTEXCOUNCIL_COMMIT=$(cat iso/cortexcouncil.ref)

for dir in packages/*/; do
  [[ $dir == packages/graceos-keyring/ ]] && dir=$keyring
  # -d: runtime dependencies are only needed on the target, not to package these. --sign uses $GPGKEY.
  (cd "$dir" && PKGDEST="$repo" makepkg -fd --cleanbuild --noconfirm --sign)
done

rm -f "$repo"/*-debug-*.pkg.tar.zst*  # makepkg's default debug split; nobody needs it
repo-add -q --verify --sign --key "$GPGKEY" "$repo/graceos.db.tar.gz" "$repo"/*.pkg.tar.zst
# repo-add makes graceos.db, graceos.files and their .sig files symlinks; release assets can't be links.
for f in graceos.db graceos.files graceos.db.sig graceos.files.sig; do
  cp --remove-destination "$(readlink -f "$repo/$f")" "$repo/$f"
done
# The public key next to the repo: build-iso.sh trusts it for a local build, and the release offers
# it to plain Arch systems (docs/install-anywhere.md).
cp "$keyring/graceos.gpg" "$repo/graceos.gpg"
ls -lh "$repo"
