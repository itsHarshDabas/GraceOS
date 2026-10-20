set -x
mount -o remount,size=5G /run/archiso/cowspace
mkdir -p /var/cache/pacman/pkg && mountpoint -q /var/cache/pacman/pkg || mount --bind /mnt/build/pkgcache /var/cache/pacman/pkg
pacman -Sy --noconfirm --needed archiso git make qemu-base edk2-ovmf python base-devel || exit 1
id builder >/dev/null 2>&1 || useradd -m builder
rm -rf /mnt/build/gos /mnt/build/work
git clone -q -b main /mnt/build/gos.bundle /mnt/build/gos && chown -R builder /mnt/build/gos || exit 1
su builder -c 'git config --global --add safe.directory "*"; cd /mnt/build/gos && build/build-packages.sh' || { echo PKG_FAILED; exit 1; }
cd /mnt/build/gos
WORK_DIR=/mnt/build/work bash build/build-iso.sh || { echo BUILD_FAILED; exit 1; }
bash build/verify-iso.sh out/graceos-*.iso | grep -E "^FAIL|ALL CHECKS|failed"
echo ISO_READY
