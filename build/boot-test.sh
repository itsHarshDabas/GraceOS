#!/usr/bin/env bash
# Headless QEMU smoke test: boot the ISO and wait until sshd inside the live system answers.
# An SSH banner proves the kernel, initramfs, systemd, networking and sshd all came up,
# without needing a login or a serial console.
# usage: boot-test.sh <iso> [bios|uefi] [timeout_seconds]   (needs qemu-base; uefi also needs edk2-ovmf)
set -euo pipefail
iso=$1; mode=${2:-bios}; limit=${3:-600}
[[ -f $iso ]] || { echo "no such ISO: $iso"; exit 2; }
[[ $mode == bios || $mode == uefi ]] || { echo "mode must be bios or uefi"; exit 2; }

tmp=$(mktemp -d)
port=$((20000 + RANDOM % 20000))
args=(-accel kvm -accel tcg -m 2048 -smp 2 -display none -no-reboot
      -cdrom "$iso" -boot d
      -nic "user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:$port-:22")
if [[ $mode == uefi ]]; then
  cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$tmp/vars.fd"
  args+=(-drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd
         -drive "if=pflash,format=raw,file=$tmp/vars.fd")
fi

qemu-system-x86_64 "${args[@]}" > "$tmp/qemu.log" 2>&1 &
qemu=$!
trap 'kill "$qemu" 2>/dev/null; wait "$qemu" 2>/dev/null; rm -rf "$tmp"' EXIT

start=$SECONDS
while (( SECONDS - start < limit )); do
  kill -0 "$qemu" 2>/dev/null || { echo "FAIL ($mode): qemu exited early"; cat "$tmp/qemu.log"; exit 1; }
  # QEMU's port forward accepts connections before the guest is up; only a real sshd sends a banner.
  banner=$(timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/$port && head -c 7 <&3" 2>/dev/null || true)
  if [[ $banner == SSH-2.0 ]]; then
    echo "PASS ($mode): sshd answered after $((SECONDS - start))s"
    exit 0
  fi
  sleep 5
done
echo "FAIL ($mode): no sshd banner within ${limit}s"
exit 1
