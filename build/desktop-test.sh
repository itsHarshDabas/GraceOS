#!/usr/bin/env bash
# Boot the ISO in QEMU with a virtual GPU and save a screenshot of whatever is on screen,
# to check that the live session reaches the Grace Candyland desktop.
# usage: desktop-test.sh out/graceos-*.iso [seconds=300] [screenshot.png]
# Without /dev/kvm this runs under TCG with software rendering: slow, so give it time.
set -euo pipefail
iso=$(realpath "$1"); wait=${2:-300}; png=$(realpath -m "${3:-out/desktop.png}")
mon=$(mktemp -u /tmp/graceos-mon.XXXXXX)
accel=(-accel tcg); [[ -w /dev/kvm ]] && accel=(-accel kvm)

qemu-system-x86_64 "${accel[@]}" -m 4096 -smp 4 -cdrom "$iso" -boot d \
  -device virtio-vga -display none -monitor "unix:$mon,server,nowait" -daemonize
sleep "$wait"

python3 - "$mon" "$png" <<'EOF'
import socket, sys, time
s = socket.socket(socket.AF_UNIX); s.connect(sys.argv[1])
for cmd in (f"screendump -f png {sys.argv[2]}", "quit"):
    s.sendall(cmd.encode() + b"\n"); time.sleep(2)
EOF
[[ -s $png ]] && echo "screenshot: $png" || { echo "no screenshot taken"; exit 1; }
