#!/usr/bin/env bash
# Tests for GraceOS Net's first-boot step (iso/net/airootfs/usr/local/bin/grace-net-setup) with fake
# curl, nmcli, pacman, df and systemctl, so it runs anywhere with bash and no network.
# usage: build/test-net-setup.sh    (as root, like the real thing: it re-runs itself through sudo otherwise)
set -euo pipefail
cd "$(dirname "$0")/.."
setup=$PWD/iso/net/airootfs/usr/local/bin/grace-net-setup
[[ $EUID -eq 0 ]] || { echo "run as root"; exit 1; }

root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
pass=0 failed=0
ok() { echo "ok   $1"; pass=$((pass + 1)); }
bad() { echo "FAIL $1"; failed=$((failed + 1)); }

make_world() {
  w=$root/$1; rm -rf "$w"; mkdir -p "$w"/{bin,net/sync,sync,cache,fake}
  export FAKE=$w/fake
  cat > "$w/net/net.conf" <<'EOF'
GRACEOS_REPO_URL=https://github.com/example/GraceOS/releases/download/net-repo-abc1234
LATEST_URL=https://github.com/example/GraceOS/releases/latest
BUILT_FROM=abc1234,\ 2026-11-23
EOF
  printf '# --- GraceOS desktop ---\ngrace-candyland\ncottoncandy\n# --- GraceOS AI ---\ncherrycolallm\n' > "$w/net/packages"
  echo "[options]" > "$w/net/pacman.conf"
  for d in core extra graceos; do echo "$d" > "$w/net/sync/$d.db"; done
  touch "$w/cache/old.pkg.tar.zst"
  echo 100000000000 > "$FAKE/avail"
  echo 0 > "$FAKE/fail_times"

  cat > "$w/bin/curl" <<'EOF'
#!/usr/bin/env bash
url=${!#}
echo "$url" >> "$FAKE/curl.log"
if [[ -e $FAKE/gone && $url == *graceos.db ]]; then printf 404; exit 0; fi
if [[ -e $FAKE/online ]]; then printf 200; exit 0; fi
printf 000; exit 7
EOF
  cat > "$w/bin/nmcli" <<'EOF'
#!/usr/bin/env bash
echo "nmcli $*" >> "$FAKE/nmcli.log"
case "$*" in
  "-t -f TYPE device") printf 'ethernet\nwifi\nloopback\n' ;;
  *"device wifi list"*) printf '40:WPA2:Home\n90:WPA2 WPA3:Cafe: Guest\n70::Open Net\n85:WPA2:\n30:WPA2:Home\n' ;;
  "--ask device wifi connect "*) touch "$FAKE/online" ;;
esac
EOF
  cat > "$w/bin/pacman" <<'EOF'
#!/usr/bin/env bash
echo "pacman $*" >> "$FAKE/pacman.log"
pk=(); fmt=
while (( $# )); do
  case $1 in --config|--print-format) [[ $1 == --print-format ]] && fmt=$2; shift 2 ;; -*) shift ;; *) pk+=("$1"); shift ;; esac
done
if grep -q -- ' -Sp ' <<< " $(tail -1 "$FAKE/pacman.log") "; then
  for p in "${pk[@]}"; do [[ $fmt == %n ]] && echo "$p" || echo 1048576; done; exit 0
fi
if grep -q -- ' -Si ' <<< " $(tail -1 "$FAKE/pacman.log") "; then
  for p in "${pk[@]}"; do printf 'Name : %s\nInstalled Size : 2.00 MiB\n' "$p"; done; exit 0
fi
n=$(( $(cat "$FAKE/installs" 2>/dev/null || echo 0) + 1 )); echo $n > "$FAKE/installs"
(( n > $(cat "$FAKE/fail_times") ))
EOF
  printf '#!/usr/bin/env bash\nprintf "Avail\\n%%s\\n" "$(cat "$FAKE/avail")"\n' > "$w/bin/df"
  printf '#!/usr/bin/env bash\necho "systemctl $*" >> "$FAKE/systemctl.log"\n' > "$w/bin/systemctl"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$w/bin/rfkill"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$w/bin/nmtui"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$w/bin/sleep"
  chmod +x "$w"/bin/*
}

run() {  # run grace-net-setup in world $w with stdin $1; output in $w/out, status in $w/rc
  set +e
  printf '%b' "$1" | env PATH="$w/bin:$PATH" GRACE_NET_DIR="$w/net" GRACE_NET_DONE="$w/done/installed" \
    GRACE_NET_SYNC="$w/sync" GRACE_NET_CACHE="$w/cache" GRACE_NET_WAIT=6 GRACE_NET_ATTEMPTS=3 \
    bash "$setup" "${@:2}" > "$w/out" 2>&1
  echo $? > "$w/rc"
  set -e
}
expect() { if eval "$2"; then ok "$1"; else bad "$1"; sed 's/^/     | /' "$w/out"; fi; }

# 1. Ethernet is up: installs every listed package from the pinned config, then marks it done.
make_world ethernet; touch "$FAKE/online"; run ""
expect "ethernet: exits 0" '[[ $(cat $w/rc) == 0 ]]'
expect "ethernet: installs all packages with the pinned pacman.conf and no -y" \
  'grep -qxF "pacman --config $w/net/pacman.conf -S --needed --noconfirm grace-candyland cottoncandy cherrycolallm" "$FAKE/pacman.log" && ! grep -q -- "-Sy" "$FAKE/pacman.log"'
expect "ethernet: ships the pinned databases into pacman's sync dir" '[[ $(cat "$w/sync/core.db" "$w/sync/extra.db" "$w/sync/graceos.db") == $(printf "core\nextra\ngraceos") ]]'
expect "ethernet: initialises the keyring first" 'grep -q "start pacman-init.service" "$FAKE/systemctl.log"'
expect "ethernet: reports sizes" 'grep -q "3 packages: 3 MiB to download, 6 MiB once installed" "$w/out"'
expect "ethernet: clears the download cache and marks done" '[[ -e $w/done/installed && ! -e $w/cache/old.pkg.tar.zst ]]'

# 2. Already done: does nothing.
run ""
expect "second run: says it's set up and doesn't touch pacman" '[[ $(cat $w/rc) == 0 ]] && grep -q "already set up" "$w/out" && [[ $(grep -c -- " -S " "$FAKE/pacman.log") == 1 ]]'

# 3. No Ethernet: Wi-Fi menu, pick network 1 (strongest first, names with colons intact, duplicates and hidden ones dropped).
make_world wifi; run "1\n1\n"
expect "wifi: exits 0 and installs" '[[ $(cat $w/rc) == 0 && -e $w/done/installed ]]'
expect "wifi: lists networks strongest first, one row each, no hidden" \
  'grep -q " 1) Cafe: Guest .*90%" "$w/out" && grep -q " 2) Open Net .*open" "$w/out" && grep -q " 3) Home .*40%" "$w/out" && ! grep -q " 4) .*%" "$w/out"'
expect "wifi: lets nmcli ask for the password" 'grep -qxF "nmcli --ask device wifi connect Cafe: Guest" "$FAKE/nmcli.log"'

# 4. Downloads fail twice, then work: retries with the same command.
make_world retry; touch "$FAKE/online"; echo 2 > "$FAKE/fail_times"; run ""
expect "retry: succeeds on attempt 3" '[[ $(cat $w/rc) == 0 ]] && grep -q "attempt 3 of 3" "$w/out" && [[ $(cat "$FAKE/installs") == 3 ]]'

# 5. Downloads keep failing: gives up after ATTEMPTS without marking done.
make_world giveup; touch "$FAKE/online"; echo 99 > "$FAKE/fail_times"; run ""
expect "give up: exits 1 after 3 attempts, not marked done" '[[ $(cat $w/rc) == 1 && ! -e $w/done/installed ]] && grep -q "failed 3 times" "$w/out"'

# 6. This build's GraceOS packages were taken down: says so and points to the newest ISO.
make_world gone; touch "$FAKE/online" "$FAKE/gone"; run ""
expect "gone: explains and links the latest release, never installs" \
  '[[ $(cat $w/rc) == 1 ]] && grep -q "too old" "$w/out" && grep -q "releases/latest" "$w/out" && ! grep -q -- " -S " "$FAKE/pacman.log" 2>/dev/null'

# 7. Offline and the user stops setup; or nobody is there to answer (no input at all).
make_world quit; run "4\n"
expect "quit: exits 1 without installing" '[[ $(cat $w/rc) == 1 && ! -e $w/done/installed && ! -e $FAKE/installs ]]'
make_world eof; run ""
expect "no input: stops instead of looping" '[[ $(cat $w/rc) == 1 && ! -e $FAKE/installs ]]'

# 8. GitHub not answering counts as offline; nothing is installed until it answers.
make_world github-down; run "3\n4\n"
expect "partly offline: keeps asking, installs nothing" '[[ $(cat $w/rc) == 1 && ! -e $FAKE/installs ]]'

# 9. Not enough RAM for the live overlay: asks, and No stops.
make_world space; touch "$FAKE/online"; echo 1000 > "$FAKE/avail"; run "n\n"
expect "low space: warns and stops on No" '[[ $(cat $w/rc) == 1 && ! -e $FAKE/installs ]] && grep -q "at least 6 GB" "$w/out"'
make_world space-yes; touch "$FAKE/online"; echo 1000 > "$FAKE/avail"; run "" --yes
expect "low space: --yes carries on" '[[ $(cat $w/rc) == 0 && -e $w/done/installed ]]'

echo "$pass passed, $failed failed"
(( failed == 0 ))
