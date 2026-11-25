import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.package import build_package


class PackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "src"
        self.source.mkdir()
        (self.source / "main.py").write_text("print('hello')\n", encoding="utf-8")
        (self.source / "requirements.txt").write_text("example==1.0\n", encoding="utf-8")
        self.output = self.root / "dist" / "agent-code.zip"

    def test_flat_package_excludes_local_files(self) -> None:
        (self.source / ".env").write_text("NOT_A_REAL_SECRET=test\n", encoding="utf-8")
        (self.source / "unexpected.py").write_text("pass\n", encoding="utf-8")
        (self.source / "__pycache__").mkdir()
        (self.source / "__pycache__" / "main.pyc").write_bytes(b"cache")

        build_package(self.source, self.output)

        with ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), ["main.py", "requirements.txt"])
            self.assertEqual(
                archive.read("main.py"), (self.source / "main.py").read_bytes()
            )
            self.assertIsNone(archive.testzip())

    def test_repeated_builds_have_identical_hashes_and_bytes(self) -> None:
        first_hash = build_package(self.source, self.output)
        first_bytes = self.output.read_bytes()
        second_hash = build_package(self.source, self.output)
        self.assertEqual(first_hash, second_hash)
        self.assertEqual(first_bytes, self.output.read_bytes())

    def test_missing_required_file_does_not_replace_existing_package(self) -> None:
        build_package(self.source, self.output)
        previous = self.output.read_bytes()
        (self.source / "requirements.txt").unlink()

        with self.assertRaisesRegex(ValueError, "requirements.txt"):
            build_package(self.source, self.output)
        self.assertEqual(previous, self.output.read_bytes())

    def test_rejects_symlinked_runtime_input(self) -> None:
        outside = self.root / "outside.txt"
        outside.write_text("not a runtime input\n", encoding="utf-8")
        (self.source / "main.py").unlink()
        try:
            (self.source / "main.py").symlink_to(outside)
        except OSError as error:
            self.skipTest(f"This machine does not permit symlink creation: {error}")

        with self.assertRaisesRegex(ValueError, "main.py"):
            build_package(self.source, self.output)
        self.assertFalse(self.output.exists())
