#!/usr/bin/env bash
# Build GraceOS's apps as .deb and .rpm packages, from the same pinned sources as packages/*
# (iso/*.ref, and toffeetwirl's release in its PKGBUILD), into out/distro/{deb,rpm}.
#   build/build-distro-packages.sh [deb|rpm|all]   (default all)
# Needs git, make, python3, node 22 + npm (Cortex Council), curl, dpkg-deb, and rpmbuild for .rpm.
# The distro-packages workflow runs it, install-tests the results in Debian, Ubuntu and Fedora,
# and publishes them as apt and dnf repos (build/publish-distro-repos.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
want=${1:-all}
out=$root/out/distro
rm -rf "$out"; mkdir -p "$out/deb" "$out/rpm"
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

MAINTAINER="GraceOS <https://github.com/itsHarshDabas/GraceOS>"

# --- sources -------------------------------------------------------------------------------
fetch() {  # name url commit -> $work/src/name at that commit; prints the version 0.rN.sha7
  local dir=$work/src/$1
  git clone -q "$2" "$dir"
  git -C "$dir" checkout -q "$3"
  printf '0.r%s.%s' "$(git -C "$dir" rev-list --count HEAD)" "$(git -C "$dir" rev-parse --short=7 HEAD)"
}

# --- packaging -----------------------------------------------------------------------------
# pkg NAME VERSION ARCH(all|amd64) SUMMARY DEB_DEPENDS RPM_REQUIRES [DEB_RECOMMENDS] [RPM_RECOMMENDS]
# packs the tree in $work/root/NAME. Dependencies are comma-separated.
pkg() {
  local name=$1 version=$2 arch=$3 summary=$4 deb_dep=$5 rpm_req=$6 deb_rec=${7:-} rpm_rec=${8:-}
  local tree=$work/root/$name
  if [[ $want == all || $want == deb ]]; then
    local d=$work/deb/$name
    rm -rf "$d"; mkdir -p "$work/deb"; cp -a "$tree" "$d"; install -d "$d/DEBIAN"
    {
      echo "Package: $name"
      echo "Version: $version"
      echo "Architecture: $arch"
      echo "Maintainer: $MAINTAINER"
      echo "Section: misc"
      echo "Priority: optional"
      echo "Homepage: https://github.com/itsHarshDabas/GraceOS"
      [[ -n $deb_dep ]] && echo "Depends: $deb_dep"
      [[ -n $deb_rec ]] && echo "Recommends: $deb_rec"
      echo "Installed-Size: $(du -sk "$tree" | cut -f1)"
      echo "Description: $summary"
      echo " Part of GraceOS: https://github.com/itsHarshDabas/GraceOS"
    } >"$d/DEBIAN/control"
    dpkg-deb --root-owner-group -Zxz --build "$d" "$out/deb/${name}_${version}_${arch}.deb" >/dev/null
  fi
  if [[ $want == all || $want == rpm ]]; then
    local r=$work/rpmbuild rpmarch=noarch
    [[ $arch == amd64 ]] && rpmarch=x86_64
    mkdir -p "$r"/{SPECS,RPMS,BUILD,BUILDROOT}
    {
      echo "Name: $name"
      echo "Version: $version"
      echo "Release: 1"
      echo "Summary: $summary"
      echo "License: LicenseRef-unspecified"
      echo "URL: https://github.com/itsHarshDabas/GraceOS"
      echo "BuildArch: $rpmarch"
      echo "AutoReqProv: no"
      local x; IFS=, read -ra x <<<"$rpm_req"; for p in "${x[@]}"; do [[ -n ${p// } ]] && echo "Requires: ${p# }"; done
      IFS=, read -ra x <<<"$rpm_rec"; for p in "${x[@]}"; do [[ -n ${p// } ]] && echo "Recommends: ${p# }"; done
      echo "%global debug_package %{nil}"
      echo "%global __os_install_post %{nil}"
      echo "%description"
      echo "$summary. Part of GraceOS: https://github.com/itsHarshDabas/GraceOS"
      echo "%install"
      echo "cp -a $tree/. %{buildroot}/"
      echo "%files"
      # Only files and links: the system's own directories (/usr/bin, ...) stay owned by filesystem.
      (cd "$tree" && find . \( -type f -o -type l \) | sed 's|^\.||; s|.*|"&"|')
      # Our own top-level directories, so removing the package removes them.
      (cd "$tree" && find . -mindepth 3 -maxdepth 3 -type d \( -path './usr/lib/*' -o -path './usr/share/grace-candyland' -o -path './opt/*' \) | sed 's|^\.|%dir |')
    } >"$r/SPECS/$name.spec"
    rpmbuild --quiet -bb --define "_topdir $r" "$r/SPECS/$name.spec"
    find "$r/RPMS" -name "$name-*.rpm" -exec mv {} "$out/rpm/" \;
  fi
  echo "$name $version"
}

tree() { rm -rf "$work/root/$1"; mkdir -p "$work/root/$1"; echo "$work/root/$1"; }

# --- the packages --------------------------------------------------------------------------
# cherrycolallm: the same layout as packages/cherrycolallm and its own packaging/build-linux.sh.
v=$(fetch cherrycolallm https://github.com/itsHarshDabas/CherryColaLLM.git "$(cat iso/cherrycolallm.ref)")
t=$(tree cherrycolallm); s=$work/src/cherrycolallm
install -d "$t/usr/lib/cherrycola"; cp -r "$s/cherrycola" "$t/usr/lib/cherrycola/"
find "$t/usr/lib/cherrycola" -name __pycache__ -prune -exec rm -rf {} +
install -Dm755 "$s/bin/cherrycolallm" "$t/usr/bin/cherrycolallm"
install -Dm755 "$s/bin/cherrycolallm-chat" "$t/usr/bin/cherrycolallm-chat"
ln -s cherrycolallm "$t/usr/bin/cherrycola"; ln -s cherrycolallm-chat "$t/usr/bin/cherrycola-chat"
install -Dm644 "$s/data/org.graceos.CherryCola.desktop" "$t/usr/share/applications/org.graceos.CherryCola.desktop"
install -Dm644 "$s/data/org.graceos.CherryCola.svg" "$t/usr/share/icons/hicolor/scalable/apps/org.graceos.CherryCola.svg"
pkg cherrycolallm "$v" all "CherryColaLLM: local AI models for GraceOS (Ollama, llama.cpp, LM Studio)" \
  "python3 (>= 3.12)" "python3 >= 3.12" \
  "python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1" "python3-gobject, gtk4, libadwaita"

# cottoncandy: its Makefile. Unlike packages/cottoncandy it leaves the default browser alone.
v=$(fetch cottoncandy https://github.com/itsHarshDabas/CottonCandy-Browser.git "$(cat iso/cottoncandy.ref)")
t=$(tree cottoncandy)
make -s -C "$work/src/cottoncandy" install DESTDIR="$t" PREFIX=/usr
pkg cottoncandy "$v" all "CottonCandy: the GraceOS web browser (Chromium through Qt WebEngine)" \
  "python3, python3-pyside6.qtcore, python3-pyside6.qtgui, python3-pyside6.qtwidgets, python3-pyside6.qtnetwork, python3-pyside6.qtsvg, python3-pyside6.qtwebenginecore, python3-pyside6.qtwebenginewidgets" \
  "python3, python3-pyside6" \
  "xdg-utils" "xdg-utils"

# cortex-council: built like packages/cortex-council (npm ci, build, prune), under /usr/lib.
v=$(fetch cortex-council https://github.com/itsHarshDabas/Cortex-Council.git "$(cat iso/cortexcouncil.ref)")
t=$(tree cortex-council); s=$work/src/cortex-council
(cd "$s" && npm ci --no-audit --no-fund --loglevel=error && npm run -s build && npm prune --omit=dev --no-audit --no-fund --loglevel=error)
install -d "$t/usr/lib/cortex-council" "$t/usr/bin"
(cd "$s" && cp -r package.json bin scripts src dist node_modules "$t/usr/lib/cortex-council/")
find "$t/usr/lib/cortex-council/node_modules" -type d -empty -delete
ln -s /usr/lib/cortex-council/bin/cortex-council.mjs "$t/usr/bin/cortex-council"
install -Dm644 "$s/README.md" "$t/usr/share/doc/cortex-council/README.md"
pkg cortex-council "$v" amd64 "Cortex Council: an AI parliament in the browser; nothing runs until you approve" \
  "nodejs (>= 22), git" "nodejs >= 22, git" "xdg-utils" "xdg-utils"

# toffeetwirl: the release tarball packages/toffeetwirl repackages, checked against its sha256.
eval "$(grep -E '^(pkgver)=' packages/toffeetwirl/PKGBUILD)"
sha=$(sed -n "s/^sha256sums=('\([0-9a-f]*\)'.*/\1/p" packages/toffeetwirl/PKGBUILD)
tarball=$work/toffeetwirl.tar.gz
curl -fsSL -o "$tarball" "https://github.com/itsHarshDabas/ToffeeTwirl-IDE/releases/download/$pkgver/ToffeeTwirl-linux-x64-$pkgver.tar.gz"
echo "$sha  $tarball" | sha256sum -c --quiet
t=$(tree toffeetwirl)
install -d "$t/opt/toffeetwirl" "$t/usr/bin"
tar -xzf "$tarball" -C "$t/opt/toffeetwirl"
ln -s /opt/toffeetwirl/bin/twirl "$t/usr/bin/twirl"
install -Dm644 packages/toffeetwirl/twirl.desktop "$t/usr/share/applications/twirl.desktop"
install -Dm644 packages/toffeetwirl/twirl-url-handler.desktop "$t/usr/share/applications/twirl-url-handler.desktop"
install -Dm644 "$t/opt/toffeetwirl/resources/app/resources/linux/code.png" "$t/usr/share/pixmaps/toffeetwirl.png"
# VS Code's own Linux runtime lists (build/linux/{debian,rpm}/dep-lists.ts), as names both
# current and older releases know.
pkg toffeetwirl "$pkgver" amd64 "ToffeeTwirl IDE: the GraceOS IDE (VS Code built with VSCodium's scripts, Grace built in)" \
  "libasound2t64 | libasound2, libatk-bridge2.0-0t64 | libatk-bridge2.0-0, libatk1.0-0t64 | libatk1.0-0, libc6, libcairo2, libcups2t64 | libcups2, libcurl4t64 | libcurl4 | libcurl3-gnutls, libdbus-1-3, libexpat1, libgbm1, libglib2.0-0t64 | libglib2.0-0, libgtk-3-0t64 | libgtk-3-0, libnspr4, libnss3, libpango-1.0-0, libsecret-1-0, libx11-6, libxcb1, libxcomposite1, libxdamage1, libxext6, libxfixes3, libxkbcommon0, libxkbfile1, libxrandr2, xdg-utils" \
  "alsa-lib, at-spi2-atk, cairo, cups-libs, dbus-libs, expat, glib2, gtk3, libX11, libXcomposite, libXdamage, libXext, libXfixes, libXrandr, libsecret, libxcb, libxkbcommon, libxkbfile, mesa-libgbm, nspr, nss, pango, xdg-utils" \
  "fonts-firacode" "fira-code-fonts"

# grace-candyland: the desktop. Only distros that package Quickshell can install it
# (Debian testing/unstable, Ubuntu's development release, Fedora).
v=$(fetch grace-candyland https://github.com/itsHarshDabas/grace-candyland.git "$(cat iso/candyland.ref)")
t=$(tree grace-candyland)
make -s -C "$work/src/grace-candyland" install DESTDIR="$t" PREFIX=/usr
pkg grace-candyland "$v" all "Grace Candyland: the GraceOS desktop (Hyprland with the Grace shell, CandySole terminal and lock screen)" \
  "hyprland, quickshell, qml6-module-qtquick, qt6-svg-plugins, fonts-inter, fonts-firacode, adwaita-icon-theme, xdg-utils, hypridle, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-vte-3.91" \
  "hyprland, quickshell, qt6-qtsvg, rsms-inter-fonts, fira-code-fonts, adwaita-cursor-theme, xdg-utils, hypridle, python3-gobject, gtk4, libadwaita, vte291-gtk4" \
  "network-manager, bluez, pipewire-pulse, wireplumber, upower, power-profiles-daemon, brightnessctl, grim, libnotify-bin, xdg-desktop-portal-hyprland, cherrycolallm" \
  "NetworkManager, bluez, pipewire-pulseaudio, wireplumber, upower, power-profiles-daemon, brightnessctl, grim, libnotify, xdg-desktop-portal-hyprland, cherrycolallm"

# grace-candyland-desktop: everything, like packages/grace-candyland-desktop (Ollama isn't in
# these distros' archives: install it from ollama.com).
t=$(tree grace-candyland-desktop)
install -Dm644 /dev/stdin "$t/usr/share/doc/grace-candyland-desktop/README" <<'EOF'
grace-candyland-desktop installs the GraceOS desktop and apps.
Start it from your login screen ("Grace Candyland") or type grace-candyland on a text console.
Ask Grace needs Ollama (https://ollama.com) and a model: cherrycolallm pull
EOF
v=$(sed -n 's/^pkgver=//p' packages/grace-candyland-desktop/PKGBUILD)
pkg grace-candyland-desktop "$v" all "The full Grace Candyland desktop: the Grace shell, CottonCandy, ToffeeTwirl, CherryColaLLM and Cortex Council" \
  "grace-candyland, cottoncandy, toffeetwirl, cherrycolallm, cortex-council, network-manager, bluez, pipewire-pulse, wireplumber, upower, power-profiles-daemon, brightnessctl, grim, libnotify-bin, xdg-desktop-portal-hyprland, nautilus, xdg-user-dirs, python3-gi, gir1.2-adw-1" \
  "grace-candyland, cottoncandy, toffeetwirl, cherrycolallm, cortex-council, NetworkManager, bluez, pipewire-pulseaudio, wireplumber, upower, power-profiles-daemon, brightnessctl, grim, libnotify, xdg-desktop-portal-hyprland, nautilus, xdg-user-dirs, python3-gobject, libadwaita" \
  "hyprsunset" "hyprsunset"

ls -lh "$out"/deb "$out"/rpm
