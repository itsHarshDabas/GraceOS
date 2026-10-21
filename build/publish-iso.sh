#!/usr/bin/env bash
# Publish the ISO that build-iso.yml just built, verified and boot-tested as a GitHub release marked Latest.
# Needs gh with GH_TOKEN, plus REPO (owner/name) and SHA (the commit that was built). Once the new release is
# up, older iso-* releases are deleted, so there is always one ISO to download.
# GitHub refuses release files of 2 GiB or more: a bigger ISO goes up in 1900 MiB parts, and the release notes
# say how to join and check them.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${REPO:?set REPO to owner/name}" "${SHA:?set SHA to the commit that was built}"

shopt -s nullglob
isos=(out/graceos-*.iso)
(( ${#isos[@]} == 1 )) || { echo "expected one ISO in out/, found ${#isos[@]}"; exit 1; }
iso=${isos[0]}
name=$(basename "$iso")
[[ -f $iso.sha256 ]] || { echo "missing $iso.sha256"; exit 1; }
version=${name#graceos-}
version=${version%-x86_64.iso}
tag="iso-$version-${SHA:0:7}"

# The ISO build's work directory takes several GB; free it before splitting (not while anything is mounted there).
work=${WORK_DIR:-/var/tmp/graceos-work}
if [[ -d $work ]] && ! grep -q " $work" /proc/mounts; then rm -rf "$work"; fi

files=("$iso.sha256")
if (( $(stat -c %s "$iso") < 2000000000 )); then
  files+=("$iso")
  get="Download \`$name\` and \`$name.sha256\`, then check it:
\`\`\`sh
sha256sum -c $name.sha256
\`\`\`"
else
  parts=out/release-parts
  rm -rf "$parts"; mkdir -p "$parts"
  split -b 1900M -d -a 2 "$iso" "$parts/$name.part"
  files+=("$parts"/*)
  get="GitHub limits release files to 2 GiB, so the ISO comes in parts. Download every \`$name.part*\` file and \`$name.sha256\` into one folder, then join and check them:
\`\`\`sh
cat $name.part* > $name
sha256sum -c $name.sha256
\`\`\`"
fi

notes="GraceOS $version, built from [\`${SHA:0:7}\`](https://github.com/$REPO/commit/$SHA) by the build-iso workflow. It passed \`verify-iso.sh\` and the BIOS and UEFI boot tests before this upload.

$get

Then write it to a USB stick or boot it in a virtual machine. The live session logs in as \`grace\` and starts the Grace Candyland desktop; \`graceinstall\` installs GraceOS to a disk."

# A re-run of the same commit replaces its release.
gh release delete "$tag" --repo "$REPO" --cleanup-tag --yes 2>/dev/null || true
gh release create "$tag" "${files[@]}" --repo "$REPO" --target "$SHA" --latest \
  --title "GraceOS $version (latest build)" --notes "$notes"

gh release list --repo "$REPO" --limit 100 --json tagName --jq '.[].tagName' | { grep '^iso-' || true; } \
  | while read -r old; do
      [[ $old == "$tag" ]] && continue
      gh release delete "$old" --repo "$REPO" --cleanup-tag --yes
    done
echo "published $tag"
