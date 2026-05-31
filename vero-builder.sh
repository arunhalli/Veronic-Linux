#!/usr/bin/env bash
# ===========================================================================
# Veronic Linux Builder  v0.2
# Minimal Linux Distribution Bootstrap Script
#
# Changes from v0.1:
#   - Colour output + section banners
#   - Strict error handling (set -euo pipefail + trap)
#   - Proper BusyBox inittab-based init (replaces single exec /bin/sh)
#   - /etc/passwd + /etc/group so login tools work
#   - Network config skeleton (lo + dhcp hook)
#   - GRUB 2 configuration (EFI + legacy BIOS via GRUB hybrid)
#   - ISOLINUX / SYSLINUX config (legacy BIOS fallback)
#   - xorriso ISO creation (if xorriso + grub-mkrescue present)
#   - Cleanup on failure via EXIT trap
#   - Build summary at the end
# ===========================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration  (override via environment)
# ---------------------------------------------------------------------------

VERO_NAME="${VERO_NAME:-Veronic Linux}"
VERO_VERSION="${VERO_VERSION:-Rolling}"
VERO_ROOT="${VERO_ROOT:-/tmp/veronic-build}"
VERO_ISO="${VERO_ISO:-veronic-latest.iso}"
BUSYBOX_VERSION="${BUSYBOX_VERSION:-1.36.1}"
ARCH="$(uname -m)"

BUSYBOX_URL="https://busybox.net/downloads/binaries/${BUSYBOX_VERSION}-x86_64-linux-musl/busybox"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
    RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'
    BLU='\033[1;34m'; CYN='\033[0;36m'; RST='\033[0m'; BLD='\033[1m'
else
    RED=''; GRN=''; YLW=''; BLU=''; CYN=''; RST=''; BLD=''
fi

info()    { echo -e "${BLU}[*]${RST} $*"; }
success() { echo -e "${GRN}[✓]${RST} $*"; }
warn()    { echo -e "${YLW}[!]${RST} $*" >&2; }
error()   { echo -e "${RED}[✗]${RST} $*" >&2; exit 1; }
section() { echo -e "\n${BLD}${CYN}── $* ──${RST}"; }

# ---------------------------------------------------------------------------
# Cleanup on failure
# ---------------------------------------------------------------------------

_cleanup() {
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        warn "Build failed (exit $rc). Partial tree left at: ${VERO_ROOT}"
    fi
}
trap _cleanup EXIT

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

section "Dependency Check"

REQUIRED_TOOLS=(wget chmod ln mkdir cat uname)
OPTIONAL_TOOLS=(xorriso grub-mkrescue mksquashfs)

for tool in "${REQUIRED_TOOLS[@]}"; do
    command -v "$tool" &>/dev/null \
        || error "Missing required tool: $tool"
done
success "Required tools present"

HAVE_ISO=false
if command -v xorriso &>/dev/null && command -v grub-mkrescue &>/dev/null; then
    HAVE_ISO=true
    success "ISO tools found (xorriso + grub-mkrescue)"
else
    warn "xorriso / grub-mkrescue not found — ISO creation step will be skipped"
fi

HAVE_SQUASH=false
if command -v mksquashfs &>/dev/null; then
    HAVE_SQUASH=true
    success "mksquashfs found — rootfs will be compressed"
fi

# ---------------------------------------------------------------------------
# Clean previous build
# ---------------------------------------------------------------------------

section "Workspace"
info "Cleaning: ${VERO_ROOT}"
rm -rf "${VERO_ROOT}"
mkdir -p "${VERO_ROOT}"
success "Workspace ready"

# ---------------------------------------------------------------------------
# Root filesystem hierarchy  (FHS subset)
# ---------------------------------------------------------------------------

section "Root Filesystem"
info "Creating directory tree ..."

mkdir -p "${VERO_ROOT}"/{bin,boot,dev,etc,home,lib,lib64,media,mnt,opt,\
proc,root,run,sbin,srv,sys,tmp,usr,var,vero}
mkdir -p "${VERO_ROOT}/usr"/{bin,lib,sbin,share,include}
mkdir -p "${VERO_ROOT}/var"/{log,cache,run,tmp,spool/mail}
mkdir -p "${VERO_ROOT}/etc"/{init.d,network,profile.d}
mkdir -p "${VERO_ROOT}/boot"/{grub,isolinux}
mkdir -p "${VERO_ROOT}/home/user"

chmod 1777 "${VERO_ROOT}/tmp"
chmod 1777 "${VERO_ROOT}/var/tmp"
chmod 0700 "${VERO_ROOT}/root"
chmod 0755 "${VERO_ROOT}/home/user"

success "Directory tree created"

# ---------------------------------------------------------------------------
# BusyBox
# ---------------------------------------------------------------------------

section "BusyBox"
info "Downloading BusyBox ${BUSYBOX_VERSION} ..."

if wget -qO "${VERO_ROOT}/bin/busybox" "${BUSYBOX_URL}"; then
    chmod +x "${VERO_ROOT}/bin/busybox"
    success "BusyBox installed"
else
    error "Failed to download BusyBox from: ${BUSYBOX_URL}"
fi

# ---------------------------------------------------------------------------
# Core utility symlinks
# ---------------------------------------------------------------------------

section "Core Utilities"
info "Creating BusyBox symlinks ..."

CORE_CMDS=(
    sh ash bash ls cp mv rm cat echo mkdir rmdir
    mount umount dmesg ps top ip ping hostname
    date dd df du grep sed awk cut sort uniq head tail wc
    tar gzip gunzip xz chmod chown ln find
    ifconfig route udhcpc
    init halt reboot poweroff
    login passwd su
    vi less more
    wget curl
    modprobe lsmod
    fdisk mkfs.ext4
    syslogd klogd
)

for cmd in "${CORE_CMDS[@]}"; do
    ln -sf /bin/busybox "${VERO_ROOT}/bin/${cmd}" 2>/dev/null || true
done

# Aliases in /usr/bin → /bin
for cmd in "${CORE_CMDS[@]}"; do
    ln -sf "/bin/${cmd}" "${VERO_ROOT}/usr/bin/${cmd}" 2>/dev/null || true
done

success "$(echo "${CORE_CMDS[@]}" | wc -w) commands linked"

# ---------------------------------------------------------------------------
# /etc/passwd, /etc/group, /etc/shadow (minimal)
# ---------------------------------------------------------------------------

section "User Database"

cat > "${VERO_ROOT}/etc/passwd" << 'EOF'
root:x:0:0:root:/root:/bin/sh
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
user:x:1000:1000:Veronic User:/home/user:/bin/sh
EOF

cat > "${VERO_ROOT}/etc/group" << 'EOF'
root:x:0:
daemon:x:1:
users:x:100:user
sudo:x:27:user
audio:x:29:user
video:x:44:user
netdev:x:109:user
EOF

cat > "${VERO_ROOT}/etc/shadow" << 'EOF'
root::19000:0:99999:7:::
user::19000:0:99999:7:::
EOF

chmod 640 "${VERO_ROOT}/etc/shadow"
success "User database written"

# ---------------------------------------------------------------------------
# System configuration
# ---------------------------------------------------------------------------

section "System Config"

echo "veronic" > "${VERO_ROOT}/etc/hostname"

cat > "${VERO_ROOT}/etc/os-release" << EOF
NAME="${VERO_NAME}"
PRETTY_NAME="${VERO_NAME} (${VERO_VERSION})"
ID=veronic
VERSION="${VERO_VERSION}"
VERSION_CODENAME=rolling
HOME_URL="https://veronic.linux/"
SUPPORT_URL="https://veronic.linux/support"
BUG_REPORT_URL="https://veronic.linux/issues"
EOF

cat > "${VERO_ROOT}/etc/fstab" << 'EOF'
# <device>    <mountpoint>  <type>    <options>           <dump> <pass>
proc          /proc         proc      defaults            0      0
sysfs         /sys          sysfs     defaults            0      0
devtmpfs      /dev          devtmpfs  defaults            0      0
tmpfs         /tmp          tmpfs     defaults,nosuid     0      0
tmpfs         /run          tmpfs     defaults,nosuid     0      0
EOF

cat > "${VERO_ROOT}/etc/profile" << 'EOF'
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export TERM="${TERM:-linux}"
export HOME="${HOME:-/root}"
export HOSTNAME="$(cat /etc/hostname 2>/dev/null || echo veronic)"
umask 022
EOF

cat > "${VERO_ROOT}/etc/profile.d/veropkg.sh" << 'EOF'
export VEROPKG_ROOT="/var/lib/veropkg/system"
EOF

# Basic loopback network
cat > "${VERO_ROOT}/etc/network/interfaces" << 'EOF'
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
EOF

# Minimal resolv.conf
cat > "${VERO_ROOT}/etc/resolv.conf" << 'EOF'
nameserver 1.1.1.1
nameserver 9.9.9.9
EOF

success "System configuration written"

# ---------------------------------------------------------------------------
# Init system  (BusyBox init + inittab)
# ---------------------------------------------------------------------------

section "Init System"
info "Creating inittab-based init ..."

# /init → symlink to busybox
ln -sf /bin/busybox "${VERO_ROOT}/init"

cat > "${VERO_ROOT}/etc/inittab" << 'EOF'
# BusyBox inittab — Veronic Linux

# Run sysinit script on boot
::sysinit:/etc/init.d/rcS

# Spawn a getty on tty1 (primary console)
tty1::respawn:/sbin/getty -L tty1 115200 linux

# Spawn a getty on ttyS0 (serial console — handy for VMs)
ttyS0::respawn:/sbin/getty -L ttyS0 115200 vt100

# Ctrl-Alt-Del → graceful reboot
::ctrlaltdel:/sbin/reboot

# Shutdown actions
::shutdown:/etc/init.d/rcK
::shutdown:/bin/umount -a -r
EOF

# sysinit script
cat > "${VERO_ROOT}/etc/init.d/rcS" << 'EOF'
#!/bin/sh
# Veronic Linux system initialisation

mount -t proc     proc     /proc
mount -t sysfs    sysfs    /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs    tmpfs    /tmp  -o nosuid
mount -t tmpfs    tmpfs    /run  -o nosuid

# Create essential /dev nodes if devtmpfs didn't do it
mknod -m 666 /dev/null  c 1 3 2>/dev/null || true
mknod -m 666 /dev/zero  c 1 5 2>/dev/null || true
mknod -m 622 /dev/tty   c 5 0 2>/dev/null || true

# Hostname
hostname -F /etc/hostname

# Seed the random pool
echo "veronic" > /dev/urandom 2>/dev/null || true

# Load kernel modules (if available)
if [ -x /sbin/modprobe ]; then
    modprobe ext4    2>/dev/null || true
    modprobe virtio  2>/dev/null || true
fi

# Bring up loopback
ip link set lo up 2>/dev/null || ifconfig lo up 2>/dev/null || true

# Start syslog
if [ -x /sbin/syslogd ]; then
    syslogd -S
    klogd
fi

echo ""
echo "================================"
echo " Welcome to Veronic Linux"
echo " Type 'veropkg help' to begin"
echo "================================"
echo ""
EOF
chmod +x "${VERO_ROOT}/etc/init.d/rcS"

# shutdown script
cat > "${VERO_ROOT}/etc/init.d/rcK" << 'EOF'
#!/bin/sh
echo "Saving system state ..."
sync
EOF
chmod +x "${VERO_ROOT}/etc/init.d/rcK"

success "Init system created (BusyBox inittab)"

# ---------------------------------------------------------------------------
# Kernel placeholder / download hint
# ---------------------------------------------------------------------------

section "Kernel"

KERNEL_DEST="${VERO_ROOT}/boot/vmlinuz"
INITRD_DEST="${VERO_ROOT}/boot/initrd.img"

if [[ -f /boot/vmlinuz-linux ]]; then
    info "Host kernel found — copying /boot/vmlinuz-linux"
    cp /boot/vmlinuz-linux "${KERNEL_DEST}"
    success "Kernel copied from host"
elif [[ -f /boot/vmlinuz ]]; then
    cp /boot/vmlinuz "${KERNEL_DEST}"
    success "Kernel copied from host"
else
    warn "No kernel found. You must supply a kernel binary."
    cat << NOTE

  Option A — copy from host:
    cp /boot/vmlinuz-\$(uname -r) ${KERNEL_DEST}

  Option B — build from source:
    git clone https://github.com/torvalds/linux
    cd linux && make defconfig && make -j\$(nproc)
    cp arch/x86/boot/bzImage ${KERNEL_DEST}

  Option C — download a pre-built tiny kernel:
    wget -O ${KERNEL_DEST} https://github.com/ivandavidov/minimal/releases/latest/download/bzImage

NOTE
fi

# ---------------------------------------------------------------------------
# initrd (cpio from rootfs, or squashfs)
# ---------------------------------------------------------------------------

section "Initrd / Root Image"

if $HAVE_SQUASH; then
    info "Building squashfs root image ..."
    mksquashfs "${VERO_ROOT}" "${VERO_ROOT}/boot/root.squashfs" \
        -comp xz -noappend -e "${VERO_ROOT}/boot" \
        > /dev/null
    success "squashfs image created at ${VERO_ROOT}/boot/root.squashfs"
else
    info "Building cpio initrd ..."
    (
        cd "${VERO_ROOT}"
        find . -not -path './boot*' \
            | cpio -oH newc 2>/dev/null \
            | gzip -9 > "${INITRD_DEST}"
    )
    success "cpio initrd created at ${INITRD_DEST}"
fi

# ---------------------------------------------------------------------------
# GRUB configuration
# ---------------------------------------------------------------------------

section "GRUB Bootloader"

cat > "${VERO_ROOT}/boot/grub/grub.cfg" << EOF
# GRUB 2 configuration — ${VERO_NAME}
set default=0
set timeout=5
set timeout_style=menu

# Theme / look
if loadfont unicode; then
    set gfxmode=auto
    insmod all_video
fi

menuentry "${VERO_NAME} (${VERO_VERSION})" {
    linux   /boot/vmlinuz  quiet loglevel=3 console=tty1 console=ttyS0,115200n8
    initrd  /boot/initrd.img
}

menuentry "${VERO_NAME} — verbose boot" {
    linux   /boot/vmlinuz  loglevel=7 console=tty1 console=ttyS0,115200n8
    initrd  /boot/initrd.img
}

menuentry "${VERO_NAME} — emergency shell" {
    linux   /boot/vmlinuz  init=/bin/sh console=tty1
    initrd  /boot/initrd.img
}

menuentry "Reboot" {
    reboot
}
EOF

success "GRUB configuration written"

# ---------------------------------------------------------------------------
# ISOLINUX / SYSLINUX (legacy BIOS fallback)
# ---------------------------------------------------------------------------

section "ISOLINUX (Legacy BIOS)"

ISOL_CFG="${VERO_ROOT}/boot/isolinux/isolinux.cfg"

# Copy isolinux.bin if syslinux is installed
if command -v syslinux &>/dev/null; then
    SYSLINUX_DIR="$(syslinux --version 2>&1 | grep -oP '/[^ ]+' | head -1 || true)"
    for candidate in /usr/lib/syslinux /usr/share/syslinux; do
        if [[ -f "${candidate}/isolinux.bin" ]]; then
            cp "${candidate}/isolinux.bin" "${VERO_ROOT}/boot/isolinux/"
            cp "${candidate}/ldlinux.c32"  "${VERO_ROOT}/boot/isolinux/" 2>/dev/null || true
            break
        fi
    done
fi

cat > "${ISOL_CFG}" << EOF
DEFAULT veronic
PROMPT  1
TIMEOUT 50
LABEL   veronic
  MENU LABEL ${VERO_NAME}
  KERNEL /boot/vmlinuz
  APPEND initrd=/boot/initrd.img quiet loglevel=3 console=tty1
LABEL   verbose
  MENU LABEL ${VERO_NAME} (verbose)
  KERNEL /boot/vmlinuz
  APPEND initrd=/boot/initrd.img loglevel=7 console=tty1
LABEL   emergency
  MENU LABEL Emergency Shell
  KERNEL /boot/vmlinuz
  APPEND initrd=/boot/initrd.img init=/bin/sh console=tty1
EOF

success "ISOLINUX configuration written"

# ---------------------------------------------------------------------------
# ISO image
# ---------------------------------------------------------------------------

section "ISO Assembly"

if $HAVE_ISO && [[ -f "${KERNEL_DEST}" ]]; then
    info "Building bootable ISO with grub-mkrescue ..."

    # grub-mkrescue wraps xorriso and handles EFI + BIOS automatically
    grub-mkrescue \
        --output="${VERO_ISO}" \
        "${VERO_ROOT}" \
        -- \
        -volid VERONIC \
        -appid "${VERO_NAME} ${VERO_VERSION}" \
        2>/dev/null

    ISO_SIZE="$(du -sh "${VERO_ISO}" | cut -f1)"
    success "ISO built: ${VERO_ISO}  (${ISO_SIZE})"
    info "Test in QEMU:"
    echo "    qemu-system-x86_64 -cdrom ${VERO_ISO} -m 512M -serial stdio"
elif $HAVE_ISO && [[ ! -f "${KERNEL_DEST}" ]]; then
    warn "ISO skipped — no kernel found at ${KERNEL_DEST}"
    info "Supply a kernel and re-run, or build manually:"
    echo ""
    echo "    grub-mkrescue --output=${VERO_ISO} ${VERO_ROOT}"
else
    warn "ISO skipped — xorriso/grub-mkrescue not available."
    info "Install them and run:"
    echo ""
    echo "    grub-mkrescue --output=${VERO_ISO} ${VERO_ROOT}"
    echo ""
    echo "  or (xorriso directly, BIOS only):"
    echo ""
    echo "    xorriso -as mkisofs -o ${VERO_ISO} \\"
    echo "      -R -J -V VERONIC \\"
    echo "      -b boot/isolinux/isolinux.bin \\"
    echo "      -no-emul-boot -boot-load-size 4 -boot-info-table \\"
    echo "      ${VERO_ROOT}"
fi

# ---------------------------------------------------------------------------
# Build summary
# ---------------------------------------------------------------------------

section "Build Summary"

echo ""
echo -e "  ${BLD}Root filesystem :${RST} ${VERO_ROOT}"
echo -e "  ${BLD}Architecture    :${RST} ${ARCH}"
echo -e "  ${BLD}BusyBox         :${RST} ${BUSYBOX_VERSION}"
echo -e "  ${BLD}Kernel          :${RST} $([ -f "${KERNEL_DEST}" ] && echo "present" || echo "MISSING")"
echo -e "  ${BLD}Initrd          :${RST} $([ -f "${INITRD_DEST}" ] && echo "present" || echo "not built")"
echo -e "  ${BLD}ISO             :${RST} $([ -f "${VERO_ISO}" ] && echo "${VERO_ISO}" || echo "not built")"
echo ""

ROOTFS_SIZE="$(du -sh "${VERO_ROOT}" 2>/dev/null | cut -f1)"
echo -e "  ${BLD}Root FS size    :${RST} ${ROOTFS_SIZE}"
echo ""

success "Veronic Linux bootstrap complete"
echo ""
echo -e "  Next steps:"
echo -e "    1. Supply a kernel → ${KERNEL_DEST}"
echo -e "    2. Add packages    → ./veropkg install <package>"
echo -e "    3. Build ISO       → grub-mkrescue --output=${VERO_ISO} ${VERO_ROOT}"
echo -e "    4. Test            → qemu-system-x86_64 -cdrom ${VERO_ISO} -m 512M"
echo ""
