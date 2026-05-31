# Security Analysis — veropkg (Veronic Linux Package Manager)

**Analyst:** Code review against v0.1 source  
**Scope:** `veropkg` Python package manager  
**Date:** 2026-05-31

---

## Executive Summary

`veropkg` has a solid architectural foundation: atomic database writes, a
transaction/rollback system, and a dedicated archive-extraction safety layer.
However, v0.1 contains several exploitable security weaknesses that could
allow privilege escalation, arbitrary file writes, or denial of service.
All critical and high findings have been fixed in v0.2.

---

## Findings

### CRITICAL-1 — Package name not validated (Path Traversal / Code Injection)

**File:** `veropkg`, `main()`, `Installer.install()`, `Remover.remove()`  
**Severity:** Critical  
**Status:** Fixed in v0.2

**Description:**  
The package name supplied on the command line was passed directly to file
system paths without any validation:

```python
# v0.1 — vulnerable
package_path = CACHE_DIR / f"{pkg}.vpkg"   # pkg = "../../etc/cron.d/evil"
```

An attacker who can influence the package name (e.g. via a malicious repo
index) could write arbitrary files anywhere on the filesystem.
The same unvalidated name was passed to `SandboxEngine` and used in
`os.execvp`, enabling shell injection on some platforms.

**Fix (v0.2):**  
`validate_package_name()` enforces the regex `^[a-zA-Z0-9][a-zA-Z0-9._+-]*$`
and a 128-character length limit before any path construction.

---

### CRITICAL-2 — `require_root()` defined but never called

**File:** `veropkg`, `main()`  
**Severity:** Critical  
**Status:** Fixed in v0.2

**Description:**  
`require_root()` was defined but never invoked. Any unprivileged user could
call `veropkg install` or `veropkg remove`, leading to world-writable files
being placed under `SYSTEM_ROOT` with `chmod 0o755`.

**Fix (v0.2):**  
`require_root()` is now called at the top of every mutating command
(`install`, `remove`, `autoremove`). It raises `VeroPkgError` (not
`sys.exit`) so the transaction can still roll back cleanly.

---

### HIGH-1 — Downloads not SSL-verified (`urllib.request.urlretrieve`)

**File:** `veropkg`, `Installer.install_package()`  
**Severity:** High  
**Status:** Fixed in v0.2

**Description:**  
```python
# v0.1 — no SSL context, vulnerable to MITM
urllib.request.urlretrieve(metadata["url"], package_path)
```
`urlretrieve` uses the default (unverified) SSL context, exposing downloads
to man-in-the-middle attacks. An attacker on the network path could replace
a package with malicious content before the SHA256 check.

The repo index was also fetched without an SSL context:
```python
with urllib.request.urlopen(REPO_URL) as response:   # no context=
```

**Fix (v0.2):**  
All network calls go through `make_ssl_context()`, which creates an
`ssl.SSLContext` with `minimum_version = TLSVersion.TLS_v1_2` and certificate
verification enabled.

---

### HIGH-2 — SHA256 verification skipped for demo packages; no size cap

**File:** `veropkg`, `Installer.install_package()`  
**Severity:** High  
**Status:** Fixed in v0.2

**Description:**  
```python
# v0.1 — skips verification wholesale when sha256 == "demo"
if expected_sha != "demo":
    ...
```
Packages with `"sha256": "demo"` in the repo index received no integrity
check at all. A malicious repo could set `sha256: "demo"` for any package to
bypass verification. Additionally, there was no cap on downloaded file size,
enabling a DoS by serving an infinitely-growing response.

**Fix (v0.2):**  
- SHA256 check now only skips if `expected_sha` is falsy **and** the URL is
  `"demo"` (the official demo sentinel). Real packages always require a hash.
- Downloads are capped at `MAX_DOWNLOAD_BYTES` (512 MB).
- The repo index is capped at `MAX_REPO_BYTES` (10 MB) via `resp.read(MAX_REPO_BYTES)`.

---

### HIGH-3 — `is_safe_path` uses `os.path.abspath`, not `os.path.realpath`

**File:** `veropkg`, `is_safe_path()`  
**Severity:** High  
**Status:** Fixed in v0.2

**Description:**  
```python
# v0.1 — symlinks not resolved
base_abs   = os.path.abspath(base)
target_abs = os.path.abspath(target)
```
`abspath` normalises `..` segments but does **not** resolve symlinks. An
attacker who plants a symlink inside the staging directory before extraction
can escape the check: `abspath("/tmp/stage/link/../../../etc")` would still
appear safe while `realpath` would expose the traversal.

**Fix (v0.2):**  
Both sides now use `os.path.realpath(os.path.abspath(...))`.

---

### MEDIUM-1 — Staging directory leaked on extraction failure

**File:** `veropkg`, `Installer.install_package()`  
**Severity:** Medium  
**Status:** Fixed in v0.2

**Description:**  
```python
# v0.1 — staging never cleaned up if tar.open() or safe_extract() raises
staging = tempfile.mkdtemp(prefix="veropkg-")
with tarfile.open(package_path) as tar:
    extracted_files = safe_extract(tar, staging)
```
If `safe_extract` raised `SecurityError` (e.g. path traversal detected), the
`staging` temp directory was left on disk indefinitely — potentially
containing partially-extracted package content.

**Fix (v0.2):**  
Wrapped in `try / finally`:
```python
try:
    staging = tempfile.mkdtemp(...)
    ...
finally:
    if staging and Path(staging).exists():
        shutil.rmtree(staging, ignore_errors=True)
```

---

### MEDIUM-2 — Non-blocking lock not used; duplicate lock files could coexist

**File:** `veropkg`, `PackageLock`  
**Severity:** Medium  
**Status:** Fixed in v0.2

**Description:**  
```python
# v0.1 — blocks indefinitely; no "already locked" error
fcntl.flock(self.fd, fcntl.LOCK_EX)
```
Using `LOCK_EX` without `LOCK_NB` blocks the second process indefinitely.
Two long-running installs could queue behind each other silently, making
the lock appear unused.

**Fix (v0.2):**  
Uses `LOCK_EX | LOCK_NB`. If the lock is unavailable, `OSError` is caught
and re-raised as a descriptive `VeroPkgError`.

---

### MEDIUM-3 — No file-size cap in `safe_extract`

**File:** `veropkg`, `safe_extract()`  
**Severity:** Medium  
**Status:** Fixed in v0.2

**Description:**  
A maliciously crafted archive member with an inflated `TarInfo.size` field
(e.g. a zip bomb) could exhaust disk space before the extraction loop
completed.

**Fix (v0.2):**  
Each member's declared `size` is checked against `MAX_DOWNLOAD_BYTES`
(512 MB) before extraction begins.

---

### MEDIUM-4 — `SandboxEngine` missing `--unshare-net` and `--die-with-parent`

**File:** `veropkg`, `SandboxEngine.build()`  
**Severity:** Medium  
**Status:** Fixed in v0.2

**Description:**  
The bubblewrap sandbox allowed the sandboxed process full network access and
continued running after the launcher process died (orphan process, no
cleanup).

**Fix (v0.2):**  
Added `--unshare-net` (no network by default) and `--die-with-parent`
(process tree cleaned up on launcher exit) to the bwrap command.

---

### LOW-1 — `run_self_tests` prints "Running self tests" twice

**File:** `veropkg`, `run_self_tests()`  
**Severity:** Low (logic bug, no security impact)  
**Status:** Fixed in v0.2

**Description:**  
The string was printed at both the function entry and inside the assertion
block, producing duplicate output that obscures test results.

---

### LOW-2 — Unused `uid` variable in `SandboxEngine.build()`

**File:** `veropkg`, `SandboxEngine.build()`  
**Severity:** Low (dead code)  
**Status:** Fixed in v0.2

**Description:**  
```python
uid = os.getuid() if hasattr(os, "getuid") else 1000
# uid is never used
```

---

### LOW-3 — `VeroPkgError` not caught in `main()`; raw tracebacks exposed

**File:** `veropkg`, `main()`  
**Severity:** Low (information disclosure)  
**Status:** Fixed in v0.2

**Description:**  
Unhandled exceptions propagated as full Python tracebacks to the terminal,
revealing internal path structure and implementation details.

**Fix (v0.2):**  
`main()` wraps the command dispatch in a `try/except (VeroPkgError, KeyboardInterrupt)`
block. In normal mode, only the error message is printed. With `--verbose`,
`log.debug("", exc_info=True)` prints the full traceback.

---

### LOW-4 — No `--version` flag

**Severity:** Low (usability)  
**Status:** Fixed in v0.2

**Description:**  
Standard tools expose `--version`. Its absence makes it hard to confirm
which build is running, complicating incident response and bug reports.

**Fix (v0.2):**  
`parser.add_argument("--version", action="version", version=f"veropkg {__version__}")`.

---

## Features Added in v0.2 (Beyond Security Fixes)

| Feature | Description |
|---|---|
| `autoremove` | Removes auto-installed packages no longer needed by any manually-installed package |
| `info <pkg>` | Displays version, status, dependencies, and installed file count |
| `search` improvements | Shows `[installed]` marker for packages already on the system |
| `list --verbose` | Shows installation timestamps |
| `--verbose` / `-v` | Enables `logging.DEBUG` output across all modules |
| `--version` | Prints `veropkg 0.2.0` |
| `remove --force` | Bypasses reverse-dependency check (with clear warning) |
| Logging | `logging.getLogger("veropkg")` throughout; debug output on `-v` |

---

## Recommendations for Future Work

1. **Package signatures** — SHA256 verifies integrity but not authenticity.
   Add GPG or minisign signatures so the repo operator can prove packages
   haven't been tampered with even if a CDN is compromised.

2. **Repo index pinning** — Pin the expected signing key fingerprint at
   install time so a compromised DNS record can't redirect to a rogue repo.

3. **Capability-based sandbox** — The current bwrap command grants read
   access to all of `/usr`. Applications should declare what they need;
   veropkg should derive the minimum `--ro-bind` set from that manifest.

4. **Delta / incremental updates** — Currently every upgrade re-downloads
   the full package. Binary diff (e.g. `bsdiff`) would reduce bandwidth and
   the attack surface of large downloads.

5. **Audit logging** — Write a tamper-evident log of every install/remove
   operation (package name, version, SHA256, timestamp, invoking UID) to
   help with incident response.

6. **`VEROPKG_ROOT` validation** — The environment variable should be
   restricted to paths under a whitelist (e.g., must start with `/opt/` or
   `/var/`) to prevent a local attacker from redirecting installs to a
   world-writable location.
