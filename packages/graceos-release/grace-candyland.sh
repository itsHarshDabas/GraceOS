# Start the Grace Candyland desktop after logging in on the first console (live ISO and installed
# systems alike). If it can't start, you stay at the prompt; type grace-candyland to try again.
if [ "$(tty)" = /dev/tty1 ] && [ -z "${WAYLAND_DISPLAY:-}" ] && [ "$(id -u)" -ge 1000 ] &&
    command -v grace-candyland >/dev/null; then
    grace-candyland || echo "The desktop didn't start. Type grace-candyland to try again."
fi
