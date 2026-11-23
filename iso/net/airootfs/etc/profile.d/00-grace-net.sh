# GraceOS Net: on the first console, download the desktop and apps before grace-candyland.sh starts
# the desktop (profile.d runs in name order). Until it finishes there is no desktop to start, so a
# stopped or failed setup leaves you at the prompt; type grace-net-setup to carry on.
if [ "$(tty)" = /dev/tty1 ] && [ -z "${WAYLAND_DISPLAY:-}" ] && [ "$(id -u)" -ge 1000 ] &&
    [ ! -e /var/lib/graceos-net/installed ]; then
    sudo /usr/local/bin/grace-net-setup ||
        echo "GraceOS Net setup didn't finish. Type grace-net-setup to try again."
fi
