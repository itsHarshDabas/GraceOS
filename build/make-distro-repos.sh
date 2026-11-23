#!/usr/bin/env bash
# Turn out/distro/{deb,rpm} into apt and dnf repos in out/repos, laid out as GitHub release assets:
#   out/repos/apt-repo/   a flat apt repo (debs, Packages, Release, InRelease, keys) -> release "apt-repo"
#   out/repos/rpm-repo/   the rpms                                                 -> release "rpm-repo"
#   out/repos/repodata/   dnf metadata, with paths relative to .../releases/download -> release "repodata"
# So apt's source is .../releases/download/apt-repo ./ and dnf's baseurl is .../releases/download.
# Signs everything with the GPG key whose fingerprint is in $GPG_KEY (already imported); with no
# key it makes an unsigned repo, which only the CI install test uses.
# Needs apt-ftparchive (apt-utils), createrepo_c, and rpmsign when signing.
set -euo pipefail
cd "$(dirname "$0")/.."
in=$PWD/out/distro
out=$PWD/out/repos
rm -rf "$out"; mkdir -p "$out/apt-repo" "$out/rpm-repo"
key=${GPG_KEY:-}

# --- apt ---
cp "$in"/deb/*.deb "$out/apt-repo/"
(
  cd "$out/apt-repo"
  apt-ftparchive packages . >Packages
  gzip -9kn Packages
  apt-ftparchive -o APT::FTPArchive::Release::Origin=GraceOS -o APT::FTPArchive::Release::Label=GraceOS \
    -o APT::FTPArchive::Release::Suite=stable -o APT::FTPArchive::Release::Codename=stable \
    -o APT::FTPArchive::Release::Description="GraceOS apps and the Grace Candyland desktop" release . >Release
  if [[ -n $key ]]; then
    gpg --batch --yes --local-user "$key" --clearsign -o InRelease Release
    gpg --batch --yes --local-user "$key" --armor --detach-sign -o Release.gpg Release
    gpg --batch --yes --armor --export "$key" >graceos.asc
    gpg --batch --yes --export "$key" >graceos-archive-keyring.gpg
  fi
)

# --- dnf ---
cp "$in"/rpm/*.rpm "$out/rpm-repo/"
if [[ -n $key ]]; then
  rpmsign --define "_gpg_name $key" --addsign "$out"/rpm-repo/*.rpm >/dev/null
  cp "$out/apt-repo/graceos.asc" "$out/rpm-repo/graceos.asc"
fi
staging=$(mktemp -d); trap 'rm -rf "$staging"' EXIT
ln -s "$out/rpm-repo" "$staging/rpm-repo"
createrepo_c --quiet "$staging"
mv "$staging/repodata" "$out/repodata"
[[ -z $key ]] || gpg --batch --yes --local-user "$key" --armor --detach-sign -o "$out/repodata/repomd.xml.asc" "$out/repodata/repomd.xml"
cat >"$out/rpm-repo/graceos.repo" <<REPO
[graceos]
name=GraceOS
baseurl=https://github.com/itsHarshDabas/GraceOS/releases/download
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=https://github.com/itsHarshDabas/GraceOS/releases/download/rpm-repo/graceos.asc
REPO
find "$out" -maxdepth 2 -type f | sort | sed "s|$out/||"
