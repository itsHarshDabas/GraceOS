#!/usr/bin/env bash
# Runs once inside the image after packages are installed (archiso calls it, then deletes it).
# Brand the OS identity. /etc/issue, the boot "Welcome to ..." line and tools like fastfetch read it.
# ID_LIKE=arch tells software that GraceOS is Arch-compatible (pacman, AUR, packages).
# shortcut: overwrites the file the `filesystem` package owns; fine on the live ISO, but an
# installed system needs a graceos-release package so pacman upgrades don't restore Arch's.
set -euo pipefail
cat > /usr/lib/os-release <<'REL'
NAME="GraceOS"
PRETTY_NAME="GraceOS"
ID=graceos
ID_LIKE=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;53;132;228"
HOME_URL="https://github.com/itsHarshDabas/GraceOS"
BUG_REPORT_URL="https://github.com/itsHarshDabas/GraceOS/issues"
LOGO=archlinux-logo
REL
