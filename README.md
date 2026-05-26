# 🐧 Veronic Linux

> *Simple. Secure. Yours.*

Veronic is a community-driven Linux distribution built for clarity, performance, and user ownership. It ships with sensible defaults, a clean desktop experience, and a package ecosystem focused on doing more with less.

---

## ✨ Features

- **Lightweight by design** — boots in under 5 seconds on modern hardware
- **Rolling release** — always up to date, no version upgrades needed
- **Veronic Desktop Environment (VDE)** — minimal, distraction-free, beautiful
- **veropkg** — native package manager with dependency resolution and sandboxing
- **Security-first** — AppArmor enabled by default, hardened kernel config
- **Privacy-respecting** — zero telemetry, zero phoning home

---

## 📦 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU       | x86_64 dual-core | x86_64 quad-core |
| RAM       | 512 MB  | 2 GB+ |
| Storage   | 8 GB    | 20 GB+ |
| Display   | 800×600 | 1920×1080 |

---

## 🚀 Getting Started

### Download

```bash
# Latest ISO (stable)
wget https://veronic.linux/releases/stable/veronic-latest.iso

# Verify checksum
sha256sum -c veronic-latest.iso.sha256
```

### Boot

Flash the ISO to a USB drive:

```bash
sudo dd if=veronic-latest.iso of=/dev/sdX bs=4M status=progress && sync
```

### Install

Boot from USB and follow the Veronic Installer (verinst). Installation takes ~10 minutes on average hardware.

---

## 🏗️ Building from Source

See [docs/building.md](docs/building.md) for full instructions.

```bash
git clone https://github.com/your-org/veronic.git
cd veronic
./build/scripts/bootstrap.sh
./build/scripts/build-iso.sh
```

---

## 📁 Repository Structure

```
veronic/
├── build/          # Build scripts and toolchain
├── bootloader/     # GRUB and EFI bootloader configs
├── configs/        # Default system configuration files
├── desktop/        # Veronic Desktop Environment (VDE)
├── docs/           # Documentation
├── init/           # Init system (veroinit)
├── installer/      # Graphical installer (verinst)
├── iso/            # ISO assembly and metadata
├── kernel/         # Kernel config and patches
└── packages/       # Core package definitions
```

---

## 🤝 Contributing

We welcome contributions of all sizes! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

- **Bug reports** → GitHub Issues
- **Security vulnerabilities** → security@veronic.linux (do not open a public issue)

---

## 🤝 Contributing
We welcome contributions of all sizes! Please read CONTRIBUTING.md before opening a pull request.

Bug reports → GitHub Issues

Security vulnerabilities → security@veronic.linux (do not open a public issue)

## 📜 License
Veronic is licensed under the GNU General Public License Version 3. See LICENSE for details.

Next Step for the License
Since you are pointing users to a LICENSE file, make sure to actually create that file in the root of your repository.

You can get the official plain-text version of the GPLv3 directly from the GNU website. In your terminal, run this inside your repository folder to download it automatically:

Bash
curl -o LICENSE https://www.gnu.org/licenses/gpl-3.0.txt
