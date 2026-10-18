[ -f ~/.bashrc ] && . ~/.bashrc

# Start the desktop on the first console. If it can't start, you stay at this prompt.
if [ "$(tty)" = /dev/tty1 ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    grace-candyland || echo "The desktop didn't start. Type grace-candyland to try again."
fi
