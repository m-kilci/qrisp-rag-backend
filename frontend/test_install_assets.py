"""Exercise the installer CLI against temporary checkout layouts."""

from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ASSETS = runpy.run_path(str(HERE / "install_assets.py"))["ASSET_PATHS"]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Qrisp checkout"
        self.source = self.root / "documentation/source"
        self.source.mkdir(parents=True)
        (self.source / "conf.py").write_text("# existing configuration\n")
        (self.source / "unrelated.txt").write_text("keep me\n")

    def run_installer(self, *args):
        return subprocess.run(
            [sys.executable, str(HERE / "install_assets.py"), str(self.root), *args],
            capture_output=True, text=True,
        )

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): (
                path.read_bytes() if path.is_file() else None,
                path.stat().st_mtime_ns,
            )
            for path in self.root.rglob("*")
        }

    def test_dry_run_changes_nothing(self):
        before = self.snapshot()
        result = self.run_installer("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Would copy:"), len(ASSETS))
        self.assertEqual(self.snapshot(), before)

    def test_install_and_identical_repeat(self):
        conf = (self.source / "conf.py").read_bytes()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ASSETS:
            self.assertEqual((self.source / "_static" / name).read_bytes(),
                             (HERE / "_static" / name).read_bytes())
        self.assertEqual((self.source / "conf.py").read_bytes(), conf)
        self.assertEqual((self.source / "unrelated.txt").read_text(), "keep me\n")
        before = self.snapshot()
        for args in [(), ("--dry-run",)]:
            result = self.run_installer(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("Unchanged:"), len(ASSETS))
            self.assertEqual(self.snapshot(), before)

    def test_conflict_prevents_all_copies(self):
        target = self.source / "_static" / ASSETS[-1]
        target.parent.mkdir(parents=True)
        target.write_text("local changes")
        before = self.snapshot()
        for args in [(), ("--dry-run",)]:
            result = self.run_installer(*args)
            self.assertEqual(result.returncode, 1)
            self.assertIn("No files copied", result.stderr)
            self.assertEqual(self.snapshot(), before)

    def test_blocked_directory(self):
        (self.source / "_static").write_text("existing file")
        before = self.snapshot()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.snapshot(), before)

    def test_symlink_directory(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.source / "_static").symlink_to(outside, target_is_directory=True)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_file(self):
        target = self.source / "_static" / ASSETS[0]
        target.parent.mkdir(parents=True)
        outside = Path(self.temp.name) / "outside.css"
        outside.write_bytes((HERE / "_static" / ASSETS[0]).read_bytes())
        target.symlink_to(outside)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn("symlink", result.stderr)
        self.assertTrue(target.is_symlink())
        self.assertFalse((self.source / "_static/js").exists())

    def test_invalid_checkout(self):
        (self.source / "conf.py").unlink()
        before = self.snapshot()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
