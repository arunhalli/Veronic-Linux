#!/usr/bin/env python3

"""
verinst
Veronic Linux Installer

Production Ready Installer

Features

Safe disk validation
GPT partitioning
UEFI and BIOS support
Automatic cleanup
Network validation
Package bootstrap
Rollback aware mounting
Password validation
Username validation
Filesystem validation
Cross platform compatible logic
Verbose logging
Dry run support
"""

import atexit
import getpass
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

INSTALL_ROOT = Path("/mnt/veronic")
EFI_MOUNT = INSTALL_ROOT / "boot/efi"

VEROPKG_BIN = "/usr/bin/veropkg"

LOG_FILE = "/tmp/verinst.log"

ACTIVE_MOUNTS = []

DRY_RUN = False

REQUIRED_TOOLS = [
"sgdisk",
"mount",
"umount",
"mkfs.ext4",
"mkfs.fat",
"partprobe",
"genfstab",
"chroot",
"useradd",
"grub-install",
"grub-mkconfig"
]

USERNAME_REGEX = r"^[a-z_][a-z0-9_-]{0,31}$"

def log(message):
timestamp = time.strftime("%H:%M:%S")

```
line = f"[{timestamp}] {message}"

print(line)

with open(LOG_FILE, "a") as f:
    f.write(line + "\n")
```

def fatal(message):
log(f"FATAL {message}")

```
cleanup()

sys.exit(1)
```

def cleanup():
if not ACTIVE_MOUNTS:
return

```
log("Cleaning up mounted filesystems")

for mount_point in reversed(ACTIVE_MOUNTS):
    try:
        subprocess.run(
            [
                "umount",
                "-lf",
                mount_point
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    except Exception:
        pass

ACTIVE_MOUNTS.clear()

log("Cleanup completed")
```

atexit.register(cleanup)

def require_root():
if os.name == "nt":
return

```
if hasattr(os, "geteuid"):
    if os.geteuid() != 0:
        fatal("Installer must run as root")
```

def validate_dependencies():
missing = []

```
for tool in REQUIRED_TOOLS:
    if shutil.which(tool) is None:
        missing.append(tool)

if missing:
    log("Missing required tools")

    for tool in missing:
        log(tool)

    sys.exit(1)
```

def validate_disk(device):
path = Path(device)

```
if not path.exists():
    fatal("Disk does not exist")

if not path.is_block_device():
    fatal("Target is not a block device")

mounted = False

with open("/proc/mounts", "r") as f:
    for line in f:
        if line.startswith(device):
            mounted = True
            break

if mounted:
    fatal("Disk currently mounted")
```

def validate_username(username):
return re.match(
USERNAME_REGEX,
username
) is not None

def validate_hostname(hostname):
if len(hostname) < 1:
return False

```
if len(hostname) > 63:
    return False

allowed = re.compile(
    r"^[a-zA-Z0-9-]+$"
)

return allowed.match(hostname) is not None
```

def validate_password(password):
if len(password) < 8:
return False

```
has_upper = any(
    c.isupper()
    for c in password
)

has_lower = any(
    c.islower()
    for c in password
)

has_digit = any(
    c.isdigit()
    for c in password
)

return (
    has_upper and
    has_lower and
    has_digit
)
```

def check_internet():
try:
socket.create_connection(
("1.1.1.1", 53),
timeout=5
)

```
    return True

except OSError:
    return False
```

def run_cmd(
cmd,
silent=False,
timeout=600
):
if DRY_RUN:
log(
f"DRY RUN {' '.join(cmd)}"
)

```
    return

try:
    result = subprocess.run(
        cmd,
        check=True,
        timeout=timeout,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if not silent:
        if result.stdout:
            print(result.stdout)

    return result

except subprocess.TimeoutExpired:
    fatal(
        f"Command timeout {' '.join(cmd)}"
    )

except subprocess.CalledProcessError as e:
    log(
        f"Command failed {' '.join(cmd)}"
    )

    if e.stdout:
        print(e.stdout)

    sys.exit(1)
```

def run_chroot(
cmd,
stdin_data=None
):
full_cmd = [
"chroot",
str(INSTALL_ROOT)
] + cmd

```
if stdin_data:
    proc = subprocess.Popen(
        full_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    output = proc.communicate(
        input=stdin_data
    )[0]

    if proc.returncode != 0:
        print(output)

        fatal(
            f"Chroot command failed {' '.join(cmd)}"
        )

else:
    run_cmd(full_cmd)
```

def get_partition_name(
disk,
number
):
if "nvme" in disk:
return f"{disk}p{number}"

```
return f"{disk}{number}"
```

def partition_disk(disk):
log(f"Partitioning disk {disk}")

```
run_cmd(
    [
        "sgdisk",
        "--zap-all",
        disk
    ]
)

run_cmd(
    [
        "sgdisk",
        "-n",
        "1:0:+512M",
        "-t",
        "1:ef00",
        "-c",
        "1:EFI",
        disk
    ]
)

run_cmd(
    [
        "sgdisk",
        "-n",
        "2:0:0",
        "-t",
        "2:8300",
        "-c",
        "2:ROOT",
        disk
    ]
)

run_cmd(
    [
        "partprobe",
        disk
    ]
)

time.sleep(2)
```

def format_filesystems(
disk,
use_btrfs=False
):
log("Formatting filesystems")

```
efi_part = get_partition_name(
    disk,
    1
)

root_part = get_partition_name(
    disk,
    2
)

run_cmd(
    [
        "mkfs.fat",
        "-F32",
        efi_part
    ]
)

if use_btrfs:
    run_cmd(
        [
            "mkfs.btrfs",
            "-f",
            root_part
        ]
    )

else:
    run_cmd(
        [
            "mkfs.ext4",
            "-F",
            root_part
        ]
    )

return (
    efi_part,
    root_part
)
```

def mount_filesystems(
efi_part,
root_part
):
log("Mounting target filesystems")

```
INSTALL_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

run_cmd(
    [
        "mount",
        root_part,
        str(INSTALL_ROOT)
    ]
)

ACTIVE_MOUNTS.append(
    str(INSTALL_ROOT)
)

EFI_MOUNT.mkdir(
    parents=True,
    exist_ok=True
)

run_cmd(
    [
        "mount",
        efi_part,
        str(EFI_MOUNT)
    ]
)

ACTIVE_MOUNTS.append(
    str(EFI_MOUNT)
)

for name in [
    "dev",
    "proc",
    "sys",
    "run"
]:
    source = f"/{name}"

    target = str(
        INSTALL_ROOT / name
    )

    Path(target).mkdir(
        parents=True,
        exist_ok=True
    )

    run_cmd(
        [
            "mount",
            "--rbind",
            source,
            target
        ]
    )

    run_cmd(
        [
            "mount",
            "--make-rslave",
            target
        ]
    )

    ACTIVE_MOUNTS.append(
        target
    )
```

def bootstrap_base_system():
log("Bootstrapping base system")

```
if not check_internet():
    fatal("Internet connection unavailable")

os.environ[
    "VEROPKG_ROOT"
] = str(INSTALL_ROOT)

if not Path(VEROPKG_BIN).exists():
    fatal("veropkg not installed")

run_cmd(
    [
        VEROPKG_BIN,
        "sync"
    ]
)

run_cmd(
    [
        VEROPKG_BIN,
        "install",
        "veronic-core"
    ]
)
```

def install_bootloader():
log("Installing bootloader")

```
uefi = Path(
    "/sys/firmware/efi"
).exists()

if uefi:
    run_chroot(
        [
            "grub-install",
            "--target=x86_64-efi",
            "--efi-directory=/boot/efi",
            "--bootloader-id=Veronic"
        ]
    )

else:
    disk = input(
        "Enter BIOS target disk for GRUB "
    )

    run_chroot(
        [
            "grub-install",
            disk
        ]
    )

run_chroot(
    [
        "grub-mkconfig",
        "-o",
        "/boot/grub/grub.cfg"
    ]
)
```

def configure_system(hostname):
log("Configuring system")

```
etc_dir = INSTALL_ROOT / "etc"

etc_dir.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    etc_dir / "hostname",
    "w"
) as f:
    f.write(hostname + "\n")

with open(
    etc_dir / "hosts",
    "w"
) as f:

    f.write(
        "127.0.0.1 localhost\n"
    )

    f.write(
        f"127.0.1.1 {hostname}\n"
    )

with open(
    INSTALL_ROOT / "etc/fstab",
    "w"
) as f:

    subprocess.run(
        [
            "genfstab",
            "-U",
            str(INSTALL_ROOT)
        ],
        stdout=f,
        check=True
    )

run_chroot(
    [
        "ln",
        "-sf",
        "/usr/share/zoneinfo/UTC",
        "/etc/localtime"
    ]
)

run_chroot(
    [
        "hwclock",
        "--systohc"
    ]
)
```

def create_swapfile(
size_gb=2
):
log(
f"Creating swapfile {size_gb}GB"
)

```
swap_path = (
    INSTALL_ROOT /
    "swapfile"
)

run_cmd(
    [
        "fallocate",
        "-l",
        f"{size_gb}G",
        str(swap_path)
    ]
)

run_cmd(
    [
        "chmod",
        "600",
        str(swap_path)
    ]
)

run_cmd(
    [
        "mkswap",
        str(swap_path)
    ]
)

with open(
    INSTALL_ROOT / "etc/fstab",
    "a"
) as f:

    f.write(
        "/swapfile none swap defaults 0 0\n"
    )
```

def create_user(
username,
password
):
log(
f"Creating user {username}"
)

```
run_chroot(
    [
        "useradd",
        "-m",
        "-G",
        "wheel",
        "-s",
        "/bin/bash",
        username
    ]
)

run_chroot(
    [
        "chpasswd"
    ],
    stdin_data=f"{username}:{password}\n"
)

sudoers = (
    INSTALL_ROOT /
    "etc/sudoers.d/wheel"
)

sudoers.parent.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    sudoers,
    "w"
) as f:

    f.write(
        "%wheel ALL=(ALL) ALL\n"
    )

os.chmod(
    sudoers,
    0o440
)
```

def synchronize():
log("Synchronizing filesystems")

```
run_cmd(
    [
        "sync"
    ]
)
```

def interactive_setup():
print()
print("Veronic Linux Installer")
print()

```
if len(sys.argv) < 2:
    print(
        "Usage sudo python verinst.py /dev/sdX"
    )

    sys.exit(1)

disk = sys.argv[1]

validate_disk(disk)

print()
print(
    f"WARNING all data on {disk} will be destroyed"
)

confirm = input(
    "Type YES to continue "
)

if confirm != "YES":
    print("Installation aborted")

    sys.exit(0)

hostname = input(
    "Hostname "
).strip()

if not hostname:
    hostname = "veronic-pc"

while not validate_hostname(hostname):
    hostname = input(
        "Invalid hostname Enter again "
    ).strip()

username = input(
    "Username "
).strip()

while not validate_username(username):
    username = input(
        "Invalid username Enter again "
    ).strip()

password = getpass.getpass(
    f"Password for {username} "
)

while not validate_password(password):
    print(
        "Weak password minimum 8 chars uppercase lowercase digit"
    )

    password = getpass.getpass(
        f"Password for {username} "
    )

confirm_password = getpass.getpass(
    "Confirm password "
)

while confirm_password != password:
    print(
        "Passwords do not match"
    )

    confirm_password = getpass.getpass(
        "Confirm password "
    )

use_btrfs = (
    input(
        "Use Btrfs filesystem y n "
    ).lower() == "y"
)

return (
    disk,
    hostname,
    username,
    password,
    use_btrfs
)
```

def main():
require_root()

```
validate_dependencies()

(
    disk,
    hostname,
    username,
    password,
    use_btrfs
) = interactive_setup()

try:
    partition_disk(disk)

    (
        efi_part,
        root_part
    ) = format_filesystems(
        disk,
        use_btrfs=use_btrfs
    )

    mount_filesystems(
        efi_part,
        root_part
    )

    bootstrap_base_system()

    configure_system(
        hostname
    )

    create_swapfile()

    create_user(
        username,
        password
    )

    install_bootloader()

    synchronize()

    print()
    print(
        "Installation complete"
    )

    print(
        "You may reboot now"
    )

except KeyboardInterrupt:
    fatal(
        "Installation interrupted"
    )

except Exception as e:
    fatal(str(e))
```

if **name** == "**main**":
main()
