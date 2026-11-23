#!/usr/bin/env bash
# Install-test the apt or dnf repo from build/make-distro-repos.sh inside a distro container.
#   build/test-distro-repos.sh BASE_URL "MUST_PACKAGES" "TRY_PACKAGES"
# BASE_URL serves out/repos (apt-repo/, rpm-repo/, repodata/). Each package is installed into
# the same system from the repo; a MUST package that fails, or fails its smoke check, fails the
# test, a TRY package is only reported. Run as root in the container (CI uses --network host).
set -uo pipefail
base=$1; must=$2; try=$3
. /etc/os-release
echo "== $PRETTY_NAME"

if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq curl ca-certificates >/dev/null
  curl -fsS "$base/apt-repo/graceos-archive-keyring.gpg" -o /usr/share/keyrings/graceos-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/graceos-archive-keyring.gpg] $base/apt-repo ./" >/etc/apt/sources.list.d/graceos.list
  apt-get update -qq || exit 1
  install_pkg() { apt-get install -y -qq --no-install-recommends "$1" >/tmp/install.log 2>&1; }
else
  sed -e "s|https://github.com/itsHarshDabas/GraceOS/releases/download|$base|" <(curl -fsS "$base/rpm-repo/graceos.repo") >/etc/yum.repos.d/graceos.repo
  dnf -q makecache --repo graceos || exit 1
  install_pkg() { dnf install -y -q --setopt=install_weak_deps=False "$1" >/tmp/install.log 2>&1; }
fi

smoke() {
  case $1 in
    cherrycolallm) cherrycolallm --help >/dev/null ;;
    cottoncandy) python3 -c 'import PySide6.QtWebEngineWidgets, PySide6.QtSvg, PySide6.QtNetwork' ;;
    cortex-council) node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' && test -x /usr/bin/cortex-council ;;
    toffeetwirl) twirl --version --no-sandbox --user-data-dir /tmp/tt | head -1 ;;
    grace-candyland) command -v Hyprland quickshell >/dev/null && test -f /usr/share/grace-candyland/hyprland.conf ;;
    *) true ;;
  esac
}

rc=0
for p in $must $try; do
  kind=TRY; [[ " $must " == *" $p "* ]] && kind=MUST
  rm -f /tmp/install.log /tmp/smoke.log
  if install_pkg "$p" && smoke "$p" >/tmp/smoke.log 2>&1; then
    echo "PASS  $p"
  else
    echo "FAIL  $p ($kind)"; cat /tmp/install.log /tmp/smoke.log 2>/dev/null | grep -v "^debconf" | tail -12 | sed "s/^/      /"
    [[ $kind == MUST ]] && rc=1
  fi
done
exit $rc
