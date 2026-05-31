#!/usr/bin/env python3
"""
test_veropkg.py — Comprehensive test suite for veropkg

Run:
    python -m pytest tests/test_veropkg.py -v
    # or
    python tests/test_veropkg.py
"""

import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make sure we import the local veropkg, not a system install
sys.path.insert(0, str(Path(__file__).parent.parent))

import veropkg as vp  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tar_gz(members: list[tuple[str, bytes]]) -> str:
    """Return path to a temporary .tar.gz containing *members*."""
    fd, path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    with tarfile.open(path, "w:gz") as tar:
        for name, content in members:
            info      = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return path


def make_symlink_tar() -> str:
    fd, path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    with tarfile.open(path, "w:gz") as tar:
        info          = tarfile.TarInfo(name="usr/bin/evil")
        info.type     = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)
    return path


def make_hardlink_tar() -> str:
    fd, path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    with tarfile.open(path, "w:gz") as tar:
        # First add a normal file so the hard-link has a target
        info      = tarfile.TarInfo(name="target.txt")
        info.size = 5
        tar.addfile(info, io.BytesIO(b"hello"))
        # Now add the hard-link
        link      = tarfile.TarInfo(name="usr/bin/evil-link")
        link.type = tarfile.LNKTYPE
        link.linkname = "target.txt"
        tar.addfile(link)
    return path

# ---------------------------------------------------------------------------
# validate_package_name
# ---------------------------------------------------------------------------

class TestValidatePackageName(unittest.TestCase):

    VALID = ["firefox", "lib32-glibc", "python3.11", "pkg+ext", "a", "X1"]
    INVALID = [
        "",                   # empty
        "../../etc/passwd",   # traversal
        "/absolute",          # absolute path
        "-starts-with-dash",  # leading dash
        "pkg;rm -rf /",       # shell injection
        "pkg$(whoami)",       # command substitution
        "`id`",               # backtick injection
        "a" * 129,            # too long
        "has space",          # whitespace
        "has\nnewline",       # newline
    ]

    def test_valid(self):
        for name in self.VALID:
            with self.subTest(name=name):
                self.assertEqual(vp.validate_package_name(name), name)

    def test_invalid(self):
        for name in self.INVALID:
            with self.subTest(name=repr(name[:30])):
                with self.assertRaises(vp.ValidationError):
                    vp.validate_package_name(name)

    def test_returns_same_string(self):
        result = vp.validate_package_name("firefox")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "firefox")

# ---------------------------------------------------------------------------
# is_safe_path
# ---------------------------------------------------------------------------

class TestIsSafePath(unittest.TestCase):

    def test_child(self):
        self.assertTrue(vp.is_safe_path("/tmp", "/tmp/example"))

    def test_nested_child(self):
        self.assertTrue(vp.is_safe_path("/tmp", "/tmp/a/b/c"))

    def test_same_path(self):
        self.assertTrue(vp.is_safe_path("/tmp", "/tmp"))

    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_traversal(self):
        self.assertFalse(vp.is_safe_path("/tmp", "/etc/passwd"))

    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_normalised_traversal(self):
        self.assertFalse(vp.is_safe_path("/tmp", "/tmp/../etc/passwd"))

    def test_prefix_collision(self):
        # /tmp2 must NOT be considered inside /tmp
        self.assertFalse(vp.is_safe_path("/tmp", "/tmp2/file"))

    def test_prefix_collision_single_char(self):
        self.assertFalse(vp.is_safe_path("/a", "/ab/file"))

# ---------------------------------------------------------------------------
# sha256sum
# ---------------------------------------------------------------------------

class TestSha256sum(unittest.TestCase):

    def _tmp(self, content: bytes) -> str:
        fd, path = tempfile.mkstemp()
        os.write(fd, content)
        os.close(fd)
        return path

    def test_known_hash(self):
        path = self._tmp(b"hello world")
        try:
            expected = hashlib.sha256(b"hello world").hexdigest()
            self.assertEqual(vp.sha256sum(path), expected)
        finally:
            os.unlink(path)

    def test_empty_file(self):
        path = self._tmp(b"")
        try:
            self.assertEqual(vp.sha256sum(path), hashlib.sha256(b"").hexdigest())
        finally:
            os.unlink(path)

    def test_returns_64_hex_chars(self):
        path = self._tmp(b"data")
        try:
            result = vp.sha256sum(path)
            self.assertRegex(result, r'^[0-9a-f]{64}$')
        finally:
            os.unlink(path)

# ---------------------------------------------------------------------------
# atomic_save_json / load_json
# ---------------------------------------------------------------------------

class TestJsonIO(unittest.TestCase):

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.json"
            vp.atomic_save_json(p, {"k": "v", "n": 1})
            self.assertEqual(vp.load_json(p), {"k": "v", "n": 1})

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.json"
            vp.atomic_save_json(p, {"v": 1})
            vp.atomic_save_json(p, {"v": 2})
            self.assertEqual(vp.load_json(p)["v"], 2)

    def test_empty_dict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.json"
            vp.atomic_save_json(p, {})
            self.assertEqual(vp.load_json(p), {})

    def test_load_missing_file(self):
        self.assertEqual(vp.load_json("/nonexistent/missing.json"), {})

    def test_produces_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.json"
            vp.atomic_save_json(p, {"nested": {"a": [1, 2, 3]}})
            with open(p) as f:
                parsed = json.load(f)   # should not raise
            self.assertEqual(parsed["nested"]["a"], [1, 2, 3])

# ---------------------------------------------------------------------------
# DependencyResolver
# ---------------------------------------------------------------------------

REPO = {
    "glibc":   {"version": "2.38",  "deps": [],                   "url": "demo", "sha256": "demo"},
    "wayland": {"version": "1.22",  "deps": ["glibc"],            "url": "demo", "sha256": "demo"},
    "mesa":    {"version": "24.0",  "deps": ["glibc", "wayland"], "url": "demo", "sha256": "demo"},
    "firefox": {"version": "123.0", "deps": ["mesa"],             "url": "demo", "sha256": "demo"},
    "standalone": {"version": "1.0", "deps": [],                  "url": "demo", "sha256": "demo"},
}


class TestDependencyResolver(unittest.TestCase):

    def setUp(self):
        self.r = vp.DependencyResolver(REPO)

    # --- basic resolution ---

    def test_resolve_single(self):
        self.assertEqual(self.r.resolve("glibc"), ["glibc"])

    def test_resolve_standalone(self):
        self.assertEqual(self.r.resolve("standalone"), ["standalone"])

    def test_resolve_firefox_contains_all(self):
        plan = self.r.resolve("firefox")
        for pkg in ("glibc", "wayland", "mesa", "firefox"):
            with self.subTest(pkg=pkg):
                self.assertIn(pkg, plan)

    def test_resolve_firefox_order(self):
        plan = self.r.resolve("firefox")
        self.assertLess(plan.index("glibc"),   plan.index("wayland"))
        self.assertLess(plan.index("wayland"),  plan.index("mesa"))
        self.assertLess(plan.index("mesa"),     plan.index("firefox"))

    def test_resolve_no_duplicates(self):
        plan = self.r.resolve("firefox")
        self.assertEqual(len(plan), len(set(plan)))

    def test_unknown_package(self):
        with self.assertRaises(vp.PackageNotFoundError):
            self.r.resolve("__nonexistent__")

    # --- circular dependency detection ---

    def _circular(self, repo):
        with self.assertRaises(vp.DependencyError):
            vp.DependencyResolver(repo).resolve(next(iter(repo)))

    def test_direct_cycle(self):
        self._circular({
            "a": {"version": "1", "deps": ["b"], "url": "demo", "sha256": "demo"},
            "b": {"version": "1", "deps": ["a"], "url": "demo", "sha256": "demo"},
        })

    def test_self_cycle(self):
        self._circular({
            "a": {"version": "1", "deps": ["a"], "url": "demo", "sha256": "demo"},
        })

    def test_three_way_cycle(self):
        self._circular({
            "a": {"version": "1", "deps": ["b"], "url": "demo", "sha256": "demo"},
            "b": {"version": "1", "deps": ["c"], "url": "demo", "sha256": "demo"},
            "c": {"version": "1", "deps": ["a"], "url": "demo", "sha256": "demo"},
        })

    def test_missing_dep_raises(self):
        broken = {
            "pkg": {"version": "1", "deps": ["ghost"], "url": "demo", "sha256": "demo"},
        }
        with self.assertRaises(vp.DependencyError):
            vp.DependencyResolver(broken).resolve("pkg")

    # --- reverse deps ---

    def test_reverse_deps(self):
        installed = {"wayland": {}, "mesa": {}}
        result = self.r.reverse_deps("glibc", installed)
        self.assertIn("wayland", result)
        self.assertIn("mesa", result)
        self.assertNotIn("firefox", result)   # not installed

    def test_reverse_deps_empty(self):
        self.assertEqual(self.r.reverse_deps("firefox", {}), [])

    def test_reverse_deps_leaf(self):
        installed = {"firefox": {}}
        # nothing installed depends on firefox
        self.assertEqual(self.r.reverse_deps("firefox", installed), [])

# ---------------------------------------------------------------------------
# safe_extract
# ---------------------------------------------------------------------------

class TestSafeExtract(unittest.TestCase):

    def test_normal_extraction(self):
        path = make_tar_gz([("usr/bin/hello", b"#!/bin/sh\necho hi\n")])
        try:
            with tempfile.TemporaryDirectory() as staging:
                with tarfile.open(path) as tar:
                    files = vp.safe_extract(tar, staging)
                self.assertIn("usr/bin/hello", files)
                self.assertTrue((Path(staging) / "usr/bin/hello").exists())
        finally:
            os.unlink(path)

    def test_path_traversal_blocked(self):
        path = make_tar_gz([("../../../etc/evil", b"evil")])
        try:
            with tempfile.TemporaryDirectory() as staging:
                with tarfile.open(path) as tar:
                    with self.assertRaises(vp.SecurityError):
                        vp.safe_extract(tar, staging)
        finally:
            os.unlink(path)

    def test_symlink_blocked(self):
        path = make_symlink_tar()
        try:
            with tempfile.TemporaryDirectory() as staging:
                with tarfile.open(path) as tar:
                    with self.assertRaises(vp.SecurityError):
                        vp.safe_extract(tar, staging)
        finally:
            os.unlink(path)

    def test_hardlink_blocked(self):
        path = make_hardlink_tar()
        try:
            with tempfile.TemporaryDirectory() as staging:
                with tarfile.open(path) as tar:
                    with self.assertRaises(vp.SecurityError):
                        vp.safe_extract(tar, staging)
        finally:
            os.unlink(path)

    def test_multiple_files(self):
        members = [
            ("usr/bin/foo", b"foo"),
            ("usr/bin/bar", b"bar"),
            ("etc/config",  b"config"),
        ]
        path = make_tar_gz(members)
        try:
            with tempfile.TemporaryDirectory() as staging:
                with tarfile.open(path) as tar:
                    files = vp.safe_extract(tar, staging)
                for name, _ in members:
                    self.assertIn(name, files)
        finally:
            os.unlink(path)

    def test_oversized_file_blocked(self):
        """A member whose declared size exceeds MAX_DOWNLOAD_BYTES is rejected."""
        fd, path = tempfile.mkstemp(suffix=".tar.gz")
        os.close(fd)
        with tarfile.open(path, "w:gz") as tar:
            info      = tarfile.TarInfo(name="huge")
            info.size = vp.MAX_DOWNLOAD_BYTES + 1
            # We don't actually write the bytes; just set the size field.
            tar.addfile(info, io.BytesIO(b""))
        try:
            with tempfile.TemporaryDirectory() as staging:
                with tarfile.open(path) as tar:
                    with self.assertRaises(vp.SecurityError):
                        vp.safe_extract(tar, staging)
        finally:
            os.unlink(path)

# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class TestTransaction(unittest.TestCase):

    def _run(self, td):
        """Helper: patch TRANSACTION_DIR, return the td path."""
        original = vp.TRANSACTION_DIR
        vp.TRANSACTION_DIR = Path(td)
        return original

    def test_commit_keeps_changes(self):
        with tempfile.TemporaryDirectory() as td:
            orig = self._run(td)
            try:
                f = Path(td) / "file.txt"
                f.write_text("original")

                with vp.Transaction() as tx:
                    tx.backup(f)
                    f.write_text("modified")
                    tx.commit()

                self.assertEqual(f.read_text(), "modified")
            finally:
                vp.TRANSACTION_DIR = orig

    def test_exception_triggers_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            orig = self._run(td)
            try:
                f = Path(td) / "file.txt"
                f.write_text("original")

                try:
                    with vp.Transaction() as tx:
                        tx.backup(f)
                        f.write_text("modified")
                        raise RuntimeError("boom")
                except RuntimeError:
                    pass

                self.assertEqual(f.read_text(), "original")
            finally:
                vp.TRANSACTION_DIR = orig

    def test_created_files_removed_on_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            orig = self._run(td)
            try:
                new_file = Path(td) / "new_file.txt"

                try:
                    with vp.Transaction() as tx:
                        new_file.write_text("new")
                        tx.register_created(new_file)
                        raise RuntimeError("abort")
                except RuntimeError:
                    pass

                self.assertFalse(new_file.exists())
            finally:
                vp.TRANSACTION_DIR = orig

# ---------------------------------------------------------------------------
# SandboxEngine
# ---------------------------------------------------------------------------

class TestSandboxEngine(unittest.TestCase):

    def test_first_arg_is_bwrap(self):
        e = vp.SandboxEngine("firefox")
        self.assertEqual(e.build_cmd()[0], "bwrap")

    def test_unshare_net_present(self):
        self.assertIn("--unshare-net", vp.SandboxEngine("firefox").build_cmd())

    def test_die_with_parent_present(self):
        self.assertIn("--die-with-parent", vp.SandboxEngine("firefox").build_cmd())

    def test_invalid_name_raises(self):
        with self.assertRaises(vp.ValidationError):
            vp.SandboxEngine("../../evil")

    def test_last_arg_is_binary_path(self):
        e = vp.SandboxEngine("firefox")
        cmd = e.build_cmd()
        self.assertIn("firefox", cmd[-1])

    def test_bwrap_not_found(self):
        e = vp.SandboxEngine("firefox")
        with patch("os.execvp", side_effect=FileNotFoundError):
            with self.assertRaises(vp.VeroPkgError):
                e.launch()

# ---------------------------------------------------------------------------
# PackageLock
# ---------------------------------------------------------------------------

class TestPackageLock(unittest.TestCase):

    def test_lock_and_release(self):
        with tempfile.TemporaryDirectory() as td:
            orig = vp.LOCKFILE
            vp.LOCKFILE = Path(td) / "veropkg.lock"
            try:
                with vp.PackageLock():
                    self.assertTrue(vp.LOCKFILE.exists())
            finally:
                vp.LOCKFILE = orig

    @unittest.skipUnless(vp.HAS_FCNTL, "fcntl not available")
    def test_double_lock_raises(self):
        with tempfile.TemporaryDirectory() as td:
            orig = vp.LOCKFILE
            vp.LOCKFILE = Path(td) / "veropkg.lock"
            try:
                with vp.PackageLock():
                    with self.assertRaises(vp.VeroPkgError):
                        with vp.PackageLock():
                            pass
            finally:
                vp.LOCKFILE = orig

# ---------------------------------------------------------------------------
# Integration: install → list → remove (using demo packages)
# ---------------------------------------------------------------------------

class TestInstallRemoveCycle(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.mkdtemp()
        # Patch all path constants to point into a temp directory
        self._orig = {
            "ROOT":            vp.ROOT,
            "CACHE_DIR":       vp.CACHE_DIR,
            "DB_DIR":          vp.DB_DIR,
            "TRANSACTION_DIR": vp.TRANSACTION_DIR,
            "LOCKFILE":        vp.LOCKFILE,
            "INSTALLED_DB":    vp.INSTALLED_DB,
            "FILES_DB":        vp.FILES_DB,
            "REPO_DB":         vp.REPO_DB,
            "SYSTEM_ROOT":     vp.SYSTEM_ROOT,
        }
        base = Path(self._td)
        vp.ROOT            = base
        vp.CACHE_DIR       = base / "cache"
        vp.DB_DIR          = base / "db"
        vp.TRANSACTION_DIR = base / "transactions"
        vp.LOCKFILE        = base / "veropkg.lock"
        vp.INSTALLED_DB    = base / "db" / "installed.json"
        vp.FILES_DB        = base / "db" / "files.json"
        vp.REPO_DB         = base / "db" / "repo.json"
        vp.SYSTEM_ROOT     = base / "system"
        vp.ensure_dirs()

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(vp, k, v)
        import shutil
        shutil.rmtree(self._td, ignore_errors=True)

    def test_install_and_verify(self):
        installer = vp.Installer(REPO)
        installer.install("glibc")
        installed = vp.load_json(vp.INSTALLED_DB)
        self.assertIn("glibc", installed)
        self.assertEqual(installed["glibc"]["version"], "2.38")
        self.assertFalse(installed["glibc"]["auto_installed"])

    def test_install_pulls_deps(self):
        vp.Installer(REPO).install("firefox")
        installed = vp.load_json(vp.INSTALLED_DB)
        for pkg in ("glibc", "wayland", "mesa", "firefox"):
            self.assertIn(pkg, installed)
        # deps are marked auto-installed
        self.assertTrue(installed["glibc"]["auto_installed"])
        self.assertFalse(installed["firefox"]["auto_installed"])

    def test_install_idempotent(self):
        vp.Installer(REPO).install("glibc")
        vp.Installer(REPO).install("glibc")   # should not raise
        installed = vp.load_json(vp.INSTALLED_DB)
        self.assertEqual(list(installed.keys()).count("glibc"), 1)

    def test_remove(self):
        vp.Installer(REPO).install("standalone")
        vp.Remover(REPO).remove("standalone")
        installed = vp.load_json(vp.INSTALLED_DB)
        self.assertNotIn("standalone", installed)

    def test_remove_blocked_by_dependent(self):
        vp.Installer(REPO).install("firefox")
        vp.Remover(REPO).remove("glibc")   # should NOT remove (firefox depends on it)
        installed = vp.load_json(vp.INSTALLED_DB)
        self.assertIn("glibc", installed)

    def test_remove_unknown(self):
        """Removing an uninstalled package should not raise."""
        vp.Remover(REPO).remove("nonexistent")   # just prints a message

    def test_autoremove_cleans_orphans(self):
        vp.Installer(REPO).install("firefox")
        # Remove firefox (the manually installed package)
        vp.Remover(REPO).remove("firefox", force=True)
        # autoremove should clean up mesa, wayland, glibc
        vp.Remover(REPO).autoremove()
        installed = vp.load_json(vp.INSTALLED_DB)
        self.assertEqual(installed, {})

# ---------------------------------------------------------------------------
# Repository.sync (mocked network)
# ---------------------------------------------------------------------------

class TestRepositorySync(unittest.TestCase):

    def test_sync_updates_repo(self):
        fake_data = json.dumps({"pkg": {"version": "9.9", "deps": [], "url": "demo", "sha256": "demo"}}).encode()

        with tempfile.TemporaryDirectory() as td:
            orig_db = vp.REPO_DB
            vp.REPO_DB = Path(td) / "repo.json"
            vp.atomic_save_json(vp.REPO_DB, {})
            try:
                mock_resp = MagicMock()
                mock_resp.__enter__ = lambda s: s
                mock_resp.__exit__  = MagicMock(return_value=False)
                mock_resp.status    = 200
                mock_resp.read      = MagicMock(return_value=fake_data)

                with patch("urllib.request.urlopen", return_value=mock_resp):
                    repo = vp.Repository()
                    repo.sync()

                loaded = vp.load_json(vp.REPO_DB)
                self.assertIn("pkg", loaded)
                self.assertEqual(loaded["pkg"]["version"], "9.9")
            finally:
                vp.REPO_DB = orig_db

    def test_sync_failure_uses_cache(self):
        """A network error should not raise — it falls back to cached repo."""
        with tempfile.TemporaryDirectory() as td:
            orig_db = vp.REPO_DB
            vp.REPO_DB = Path(td) / "repo.json"
            vp.atomic_save_json(vp.REPO_DB, {"cached_pkg": {"version": "1.0", "deps": [], "url": "demo", "sha256": "demo"}})
            try:
                with patch("urllib.request.urlopen", side_effect=OSError("network error")):
                    repo = vp.Repository()
                    repo.sync()   # should not raise

                # Cached data should remain
                loaded = vp.load_json(vp.REPO_DB)
                self.assertIn("cached_pkg", loaded)
            finally:
                vp.REPO_DB = orig_db


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
