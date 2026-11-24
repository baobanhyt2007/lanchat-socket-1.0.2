"""Smoke tests for the ways a user can start the program.

These catch a regression the library tests miss: relative imports can break
while every module still imports fine on its own.
"""

import subprocess
import sys
import unittest
from pathlib import Path

from lanchat import __version__

ROOT = Path(__file__).resolve().parents[1]


class EntryPointTests(unittest.TestCase):
    def run_python(self, *args):
        return subprocess.run(
            [sys.executable] + list(args),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=30,
        )

    def test_package_imports_cleanly(self):
        app = __import__("lanchat.app", fromlist=["App"])
        protocol = __import__("lanchat.protocol", fromlist=["encode_msg"])
        self.assertTrue(hasattr(app, "App"))
        self.assertTrue(callable(protocol.encode_msg))

    def test_module_entry_point(self):
        result = self.run_python("-m", "lanchat", "--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(__version__, result.stdout)

    def test_script_entry_point(self):
        result = self.run_python(
            str(ROOT / "lanchat" / "__main__.py"), "--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(__version__, result.stdout)

    def test_help_lists_required_options(self):
        result = self.run_python("-m", "lanchat", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for option in ("--name", "--port", "--udp-port", "--bcast"):
            self.assertIn(option, result.stdout)


if __name__ == "__main__":
    unittest.main()
