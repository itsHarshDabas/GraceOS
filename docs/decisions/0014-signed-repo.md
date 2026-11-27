# 0014: The [graceos] repo is signed, and pacman requires it

- Status: proposed, 2026-11-27. Harsh asked to "fix" the unsigned repo called out in ADR 0006.
- Task: T-029.

## Context
ADR 0006 shipped `[graceos]` as `SigLevel = Optional TrustAll`: packages came over HTTPS from GitHub
Releases, but nothing proved GraceOS built them, and anyone who could replace a release asset could
ship code to every GraceOS machine. The apt and dnf repos (ADR 0012) are already signed with the
`GRACEOS_SIGNING_KEY` secret.

## Decision
- **One key** for pacman, apt and dnf: the `GRACEOS_SIGNING_KEY` Actions secret (an armored ed25519 key
  without a passphrase). `build/new-signing-key.sh` makes it once on Harsh's computer, stores it with
  `gh secret set`, saves an offline backup, and writes the public half to `packages/graceos-keyring/`.
  The private key is never in the repo, the ISO or a log.
- **`graceos-keyring`** installs `graceos.gpg`, `graceos-trusted` and `graceos-revoked` in
  `/usr/share/pacman/keyrings/`, the layout `archlinux-keyring` uses. Its install script runs
  `pacman-key --populate graceos` when a keyring exists. It is in the `[minimal]` ISO section (so every
  GraceOS install has it) and a dependency of `grace-candyland-desktop`.
- **Signing:** `build/build-packages.sh` needs `GPGKEY` and runs `makepkg --sign` for every package and
  `repo-add --verify --sign` for the database, so the release holds `*.pkg.tar.zst.sig`,
  `graceos.db.sig`, `graceos.files.sig` and `graceos.gpg`. It refuses a key other than the committed one
  unless `ALLOW_TEST_KEY=1`.
- **Requiring it:** `iso/pacman.conf` has `SigLevel = Required` for `[graceos]`; `graceinstall` and the
  archinstall profile pass `Required` / `TrustedOnly`.
- **Trust path:**
  - ISO build: `build-iso.sh` adds the signing key to the build machine's pacman keyring and
    locally signs it, because mkarchiso checks packages with that keyring.
  - Live ISO: `pacman-init.service` runs `pacman-key --populate` (all keyrings), which includes graceos.
  - graceinstall: pacstrap checks with the live keyring; `graceos-keyring`'s install script then adds the
    key to the new system's keyring (pacstrap `-K` makes it empty).
  - GraceOS Net: `graceos.db.sig` ships next to the pinned `graceos.db`.
  - Plain Arch: three commands in `docs/install-anywhere.md` add the key from the repo, then
    `graceos-keyring` keeps it.
- **CI:** `packages.yml` and main/manual `build-iso.yml` runs use the real key. Pull requests sign with a
  throwaway test key and a graceos-keyring built with it, so unreviewed code is never signed with the
  real key, and PR runs never publish.

## Consequences
- pacman refuses a package or database that the GraceOS key didn't sign.
- **Until `build/new-signing-key.sh` has run and its two files are committed, main can't publish:**
  `packages.yml` and `build-iso.yml` stop with "GRACEOS_SIGNING_KEY is not set" or a key mismatch.
- A key change (lost or leaked) is a new `graceos-keyring` release signed by the old key while it still
  works; otherwise users re-add the key by hand. Revoked fingerprints go in `graceos-revoked`.
- Systems installed before this change have `Optional TrustAll` in `/etc/pacman.conf`; they keep working
  (signed packages pass that too) but stay unenforced until they change that line to `Required`.
