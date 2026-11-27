#!/usr/bin/env bash
# Make the GraceOS signing key, once. Run it on your own computer (Linux, macOS or Git Bash) with gpg
# and a logged-in GitHub CLI (`gh auth login`). It:
#   1. generates an ed25519 signing key in a throwaway GnuPG home,
#   2. stores the private key as the GRACEOS_SIGNING_KEY Actions secret (`gh secret set`; it never
#      touches the repo or your terminal),
#   3. writes the public key to packages/graceos-keyring/ (commit those two files),
#   4. saves the private key to the backup file you name, for an offline copy (a USB stick, a
#      password manager). Without it, a lost secret means a new key and a new graceos-keyring.
# The same secret already signs the apt and dnf repos (distro-packages.yml), so they use this key too.
# usage: build/new-signing-key.sh BACKUP_FILE
#        build/new-signing-key.sh --existing FINGERPRINT   # reuse a key from your own keyring instead
set -euo pipefail
cd "$(dirname "$0")/.."
dir=packages/graceos-keyring
command -v gpg >/dev/null || { echo "needs gpg"; exit 1; }

write_public() {  # $1 = gpg home, $2 = fingerprint
  gpg --homedir "$1" --batch --yes --export "$2" > "$dir/graceos.gpg"
  echo "$2:4:" > "$dir/graceos-trusted"
  echo "Wrote $dir/graceos.gpg and $dir/graceos-trusted (fingerprint $2)."
}

if [[ ${1:-} == --existing ]]; then
  fpr=${2:?usage: $0 --existing FINGERPRINT}
  write_public "${GNUPGHOME:-$HOME/.gnupg}" "$fpr"
  echo "Make sure GRACEOS_SIGNING_KEY holds this key's private part (gpg --armor --export-secret-keys $fpr)."
  exit 0
fi

backup=${1:?usage: $0 BACKUP_FILE (where to save the private key for an offline copy)}
[[ ! -e $backup ]] || { echo "$backup exists; pick a new file"; exit 1; }
[[ ! -s $dir/graceos.gpg ]] || { echo "$dir/graceos.gpg already has a key; delete it first if you really want a new one"; exit 1; }
command -v gh >/dev/null || { echo "needs the GitHub CLI (gh), logged in"; exit 1; }

home=$(mktemp -d); trap 'rm -rf "$home"' EXIT
gpg --homedir "$home" --batch --passphrase '' --quick-gen-key "GraceOS packages <https://github.com/itsHarshDabas/GraceOS>" ed25519 sign never
fpr=$(gpg --homedir "$home" --list-secret-keys --with-colons | awk -F: '/^fpr/ { print $10; exit }')
( umask 077; gpg --homedir "$home" --batch --armor --export-secret-keys "$fpr" > "$backup" )
gh secret set GRACEOS_SIGNING_KEY --repo itsHarshDabas/GraceOS < "$backup"
write_public "$home" "$fpr"
echo "Saved the private key to $backup: move it somewhere offline and safe."
echo "Next: git add $dir/graceos.gpg $dir/graceos-trusted && git commit -m 'packages: add the GraceOS signing key'"
