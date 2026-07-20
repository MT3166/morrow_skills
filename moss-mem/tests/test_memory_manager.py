import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory_manager.py"


class MemoryManagerCLITest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_cli_help_loads_on_python39(self):
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("MOSS_MEM", result.stdout)

    def test_state_set_acquires_lock_and_updates_memory(self):
        result = self.run_cli(
            "state",
            "set",
            "current_task=repair login",
            "next_step=inspect auth.py",
            "status=🔧",
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        memory = (self.project / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("repair login", memory)
        self.assertIn("inspect auth.py", memory)
        self.assertFalse((self.project / ".moss-mem/tasks/.edit_lock").exists())
