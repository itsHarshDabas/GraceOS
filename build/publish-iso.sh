#!/usr/bin/env bash
# Publish the two ISOs that build-iso.yml just built, verified and boot-tested as one GitHub release marked Latest:
#   out/graceos-<date>-x86_64.iso       GraceOS (Full): everything on the ISO
#   out/graceos-net-<date>-x86_64.iso   GraceOS Net: the base only; downloads the desktop and apps at first boot
# plus out/net-repo, the GraceOS packages that this Net ISO downloads, as their own net-repo-<sha7> release
# (build-iso.sh net wrote that URL into the ISO). The newest five net-repo releases are kept, so a Net ISO
# keeps working for a few releases after it stops being the latest.
# Needs gh with GH_TOKEN, plus REPO (owner/name) and SHA (the commit that was built). Once the new release is
# up, older iso-* releases are deleted, so there is always one release to download from.
# GitHub refuses release files of 2 GiB or more: a bigger ISO goes up in 1900 MiB parts, and the release notes
# say how to join and check them.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${REPO:?set REPO to owner/name}" "${SHA:?set SHA to the commit that was built}"
KEEP_NET_REPOS=${KEEP_NET_REPOS:-5}

shopt -s nullglob
one() {  # the single file matching a glob
  local -a f=("$@")
  (( ${#f[@]} == 1 )) || { echo "expected one ${1##*/} in out/, found ${#f[@]}" >&2; exit 1; }
  [[ -f ${f[0]}.sha256 ]] || { echo "missing ${f[0]}.sha256" >&2; exit 1; }
  echo "${f[0]}"
}
full=$(one out/graceos-[0-9]*.iso)
net=$(one out/graceos-net-[0-9]*.iso)
[[ -f out/net-repo/graceos.db ]] || { echo "missing out/net-repo (the Net ISO's packages)"; exit 1; }
version=$(basename "$full"); version=${version#graceos-}; version=${version%-x86_64.iso}
tag="iso-$version-${SHA:0:7}"
net_tag="net-repo-${SHA:0:7}"

# The ISO build's work directory takes several GB; free it before splitting (not while anything is mounted there).
work=${WORK_DIR:-/var/tmp/graceos-work}
if [[ -d $work ]] && ! grep -q " $work" /proc/mounts; then rm -rf "$work"; fi

# Release files for one ISO: the ISO itself, or 1900 MiB parts of it when it's 2 GiB or more.
files=()
add_iso() {
  local iso=$1 parts
  files+=("$iso.sha256")
  if (( $(stat -c %s "$iso") < 2147483648 )); then
    files+=("$iso")
  else
    parts=out/release-parts/$(basename "$iso")
    rm -rf "$parts"; mkdir -p "$parts"
    split -b 1900M -d -a 2 "$iso" "$parts/$(basename "$iso").part"
    files+=("$parts"/*)
  fi
}
# How to download and check one ISO, for the release notes.
how_to_get() {
  local name; name=$(basename "$1")
  if (( $(stat -c %s "$1") < 2147483648 )); then
    printf 'Download `%s` and `%s.sha256`, then check it:\n```sh\nsha256sum -c %s.sha256\n```' "$name" "$name" "$name"
  else
    printf 'GitHub limits release files to 2 GiB, so this ISO comes in parts. Download every `%s.part*` file and `%s.sha256` into one folder, then join and check them:\n```sh\ncat %s.part* > %s\nsha256sum -c %s.sha256\n```' \
      "$name" "$name" "$name" "$name" "$name"
  fi
}
mib() { echo $(( $(stat -c %s "$1") / 1048576 )); }
add_iso "$full"
add_iso "$net"
get_full=$(how_to_get "$full")
get_net=$(how_to_get "$net")

# Net's packages go up first, so a published Net ISO never points at a missing release.
gh release delete "$net_tag" --repo "$REPO" --cleanup-tag --yes 2>/dev/null || true
gh release create "$net_tag" out/net-repo/* --repo "$REPO" --target "$SHA" --prerelease --latest=false \
  --title "GraceOS Net packages (${SHA:0:7})" \
  --notes "The GraceOS packages that the GraceOS Net ISO built from [\`${SHA:0:7}\`](https://github.com/$REPO/commit/$SHA) downloads at first boot. You don't need to download anything here: grace-net-setup does, and checks each file against the package database on the ISO. Kept for the newest $KEEP_NET_REPOS builds."

notes="GraceOS $version, built from [\`${SHA:0:7}\`](https://github.com/$REPO/commit/$SHA) by the build-iso workflow. Both images passed \`verify-iso.sh\` and the BIOS and UEFI boot tests before this upload.

### GraceOS: \`$(basename "$full")\` ($(mib "$full") MiB)
Everything is on the ISO, so the live desktop works without the internet.

$get_full

### GraceOS Net: \`$(basename "$net")\` ($(mib "$net") MiB)
The smaller, online image: it carries the base system only. At first boot it connects to the internet (Ethernet by itself, Wi-Fi from a menu), downloads the Grace Candyland desktop and the GraceOS apps (CottonCandy, CandySole, ToffeeTwirl, CherryCola, Ask Grace, Grace Settings, Cortex Council), then starts the desktop. It needs the internet, and enough RAM to hold the downloaded desktop (setup checks and tells you). What it downloads is pinned to this build: Arch packages from that day's Arch Linux Archive snapshot and GraceOS packages from the [\`$net_tag\`](https://github.com/$REPO/releases/tag/$net_tag) release, each checked against the package databases on the ISO.

$get_net

Then write either one to a USB stick or boot it in a virtual machine. The live session logs in as \`grace\` and starts the Grace Candyland desktop; \`graceinstall\` installs GraceOS to a disk (over the internet, with either image). Windows app support stays optional: \`grace-wine install\`."

# A re-run of the same commit replaces its release.
gh release delete "$tag" --repo "$REPO" --cleanup-tag --yes 2>/dev/null || true
gh release create "$tag" "${files[@]}" --repo "$REPO" --target "$SHA" --latest \
  --title "GraceOS $version (latest build)" --notes "$notes"

releases=$(gh release list --repo "$REPO" --limit 200 --json tagName,createdAt --jq 'sort_by(.createdAt) | reverse | .[].tagName')
{ grep '^iso-' <<< "$releases" || true; } | while read -r old; do
  [[ $old == "$tag" ]] && continue
  gh release delete "$old" --repo "$REPO" --cleanup-tag --yes
done
{ grep '^net-repo-' <<< "$releases" || true; } | tail -n +$((KEEP_NET_REPOS + 1)) | while read -r old; do
  [[ $old == "$net_tag" ]] && continue
  gh release delete "$old" --repo "$REPO" --cleanup-tag --yes
done
echo "published $tag and $net_tag"
