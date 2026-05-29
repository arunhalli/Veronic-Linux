# Security Policy

## Veronic Linux Security Policy

Veronic Linux is committed to maintaining a secure, privacy-respecting, and transparent operating system. This document explains how security vulnerabilities are handled, how to report issues responsibly, and what users can expect regarding security updates and support.

---

# Supported Versions

The following release branches currently receive security updates:

| Version                    | Supported |
| -------------------------- | --------- |
| Rolling Stable             | ✅ Yes     |
| Rolling Testing            | ⚠ Limited |
| Legacy / Archived Releases | ❌ No      |

Only officially supported versions receive:

* Security patches
* Critical bug fixes
* Package signature updates
* Kernel hardening updates
* Repository metadata verification

Users are strongly encouraged to keep systems updated.

---

# Reporting a Vulnerability

If you discover a security vulnerability in Veronic Linux, please report it responsibly.

## Contact

Send reports to:

```text
security@veroniclinux.org
```

Alternatively, private reports may be submitted through the official project repository security advisory system.

---

# What to Include

Please provide as much information as possible:

* Affected component or package
* Veronic Linux version
* Steps to reproduce
* Expected behavior
* Actual behavior
* Logs, screenshots, or proof-of-concept
* Potential impact assessment
* Suggested mitigation (optional)

Incomplete reports may slow investigation.

---

# Responsible Disclosure Policy

We ask researchers and contributors to follow responsible disclosure practices:

* Do not publicly disclose vulnerabilities before a fix is available
* Do not intentionally access private user data
* Do not disrupt public infrastructure or services
* Allow maintainers reasonable time to investigate and patch issues
* Avoid destructive testing on production systems

We value security research and responsible reporting.

---

# Security Response Process

After a report is received:

1. The report is acknowledged
2. Severity and impact are assessed
3. Maintainers reproduce the issue
4. A fix or mitigation is developed
5. Security updates are released
6. A public advisory may be published

Critical vulnerabilities are prioritized immediately.

---

# Severity Classification

| Severity | Description                                                  |
| -------- | ------------------------------------------------------------ |
| Critical | Remote code execution, full system compromise                |
| High     | Privilege escalation, authentication bypass                  |
| Medium   | Limited security impact or partial compromise                |
| Low      | Minor issues, information disclosure, hardening improvements |

Severity ratings may vary depending on exploitability and real-world impact.

---

# Security Update Distribution

Security updates are delivered through the official Veronic Linux repositories.

Update your system regularly:

```bash
sudo veropkg sync
sudo veropkg upgrade
```

Using outdated systems may expose users to known vulnerabilities.

---

# Package Signing & Verification

All official Veronic Linux packages are cryptographically signed.

Verify package integrity:

```bash
veropkg verify package-name
```

Refresh trusted signing keys:

```bash
sudo veropkg keys refresh
```

Unsigned or unofficial packages are not supported.

---

# Default Security Features

Veronic Linux includes multiple security-focused technologies:

* AppArmor enforcement
* Hardened kernel configuration
* Address Space Layout Randomization (ASLR)
* Sandboxed applications
* User permission isolation
* Secure package signatures
* Firewall integration
* Secure Boot support

Security defaults may evolve over time as the project improves.

---

# Recommended Security Practices

Users are encouraged to:

* Enable full-disk encryption
* Keep Secure Boot enabled
* Install updates regularly
* Use strong passwords
* Avoid daily root usage
* Use multi-factor authentication where available
* Install software only from trusted repositories
* Review system logs periodically

---

# Third-Party Repositories

Third-party repositories and unofficial packages may introduce security risks.

Veronic Linux cannot guarantee the safety of:

* Community-maintained repositories
* Unverified packages
* Modified kernels
* Unsupported system modifications

Users assume responsibility for external software sources.

---

# End-of-Life Policy

Unsupported releases no longer receive:

* Security patches
* Package updates
* Repository maintenance
* Vulnerability fixes

Users should upgrade immediately when a release reaches end-of-life status.

---

# Security Transparency

Veronic Linux believes in transparent security practices.

Where possible, the project aims to provide:

* Public security advisories
* Open-source fixes
* Reproducible builds
* Transparent changelogs
* Community auditing

---

# Legal Notice

This project is provided “as is” without warranties of any kind. While every effort is made to maintain system security, users are responsible for properly securing their own environments and infrastructure.

---

# Contact

Security Team:

```text
security@veroniclinux.org
```

Project Website:

```text
https://veroniclinux.org
```
