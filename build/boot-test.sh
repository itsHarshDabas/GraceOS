#!/usr/bin/env bash
# Headless QEMU smoke test: boot the ISO and wait for the live shell prompt on the serial console.
# usage: boot-test.sh out/graceos-*.iso [bios|uefi]   (uefi needs the `edk2-ovmf` package)
set -euo pipefail
iso=$1; mode=${2:-bios}
args=(-m 2048 -cdrom "$iso" -boot d -display none -serial mon:stdio -no-reboot)
[[ $mode == uefi ]] && args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd)
log=$(mktemp)
timeout 300 qemu-system-x86_64 "${args[@]}" 2>&1 | tee "$log" | grep -m1 -E 'graceos login|root@graceos' >/dev/null \
  && { echo "PASS ($mode)"; exit 0; } || { echo "FAIL ($mode); tail:"; tail -20 "$log"; exit 1; }
