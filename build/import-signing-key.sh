#!/usr/bin/env bash
# CI helper: put the GraceOS signing key into the current user's gpg and print its fingerprint.
# The key comes from $GRACEOS_SIGNING_KEY (an armored private key without a passphrase). When that is
# empty and ALLOW_TEST_KEY=1 (pull requests from forks, which get no secrets), it makes a one-day
# test key instead; build-packages.sh then puts that key in this build's graceos-keyring, so the
# test ISO is consistent, and such builds are never published.
set -euo pipefail
if [[ -n ${GRACEOS_SIGNING_KEY:-} ]]; then
  printf '%s\n' "$GRACEOS_SIGNING_KEY" | gpg --batch --quiet --import
elif [[ ${ALLOW_TEST_KEY:-} == 1 ]]; then
  echo "GRACEOS_SIGNING_KEY is not set: signing with a throwaway test key" >&2
  gpg --batch --quiet --yes --passphrase '' --quick-gen-key "GraceOS CI test key" ed25519 sign 1d
else
  echo "GRACEOS_SIGNING_KEY is not set. Run build/new-signing-key.sh once (docs/decisions/0014-signed-repo.md)." >&2
  exit 1
fi
gpg --list-secret-keys --with-colons | awk -F: '/^fpr/ { print $10; exit }'
