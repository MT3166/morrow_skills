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
SPEC = importlib.util.spec_from_file_location("memory_manager", SCRIPT)
memory_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(memory_manager)


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

    def test_knowledge_index_contains_memory_tasks_archives_and_summaries(self):
        (self.project / ".moss-mem/tasks/archive/2026").mkdir(parents=True)
        (self.project / ".moss-mem/summaries").mkdir(parents=True)
        (self.project / "MEMORY.md").write_text(
            "# MEMORY.md\n\n## 下一步指令 [Strict]\n- run tests\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/tasks/20260720-100000_task.md").write_text(
            "# Task - Login\n\n## Description\nRepair login\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/tasks/archive/2026/20260719_task.md").write_text(
            "# Compacted Login Task\n\n## Key Decisions\ntoken refresh race\n",
            encoding="utf-8",
        )
        (self.project / ".moss-mem/summaries/20260720-auth.md").write_text(
            "---\ntopic: auth summary\ncreated: 2026-07-20 10:00\n---\n\n# Harness Summary\n\n## Summary\nUse httpOnly cookie\n",
            encoding="utf-8",
        )

        result = self.run_cli("knowledge-index")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        json_path = self.project / ".moss-mem/index-cache/memory-index.json"
        md_path = self.project / ".moss-mem/index-cache/memory-index.md"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["records"]), 4)
        self.assertEqual(
            {record["kind"] for record in payload["records"]},
            {"memory", "task", "archived-task", "summary"},
        )
        self.assertIn("token refresh race", json_path.read_text(encoding="utf-8"))
        self.assertIn("auth summary", md_path.read_text(encoding="utf-8"))

    def test_index_record_parses_frontmatter_sections_and_preview_limit(self):
        source = self.project / "task.md"
        long_text = "x" * 300
        source.write_text("---\ntopic: Topic\ncreated: 2026-07-20\n---\n# Heading\n\n## Description\n" + long_text + "\n## Notes\nvalue\n", encoding="utf-8")
        with mock.patch.object(memory_manager, "MEMORY_FILE", str(self.project / "missing.md")):
            record = memory_manager._parse_memory_record(source, 7)
        self.assertEqual(record["title"], "Topic")
        self.assertEqual(record["created"], "2026-07-20")
        self.assertEqual(record["sections"]["Notes"], "value")
        self.assertEqual(len(record["preview"]), 240)

    def test_tokenize_includes_unique_sorted_cjk_terms(self):
        terms = memory_manager._tokenize("Alpha 中文测试 中文")
        self.assertEqual(sorted(set(terms)), sorted(set(["alpha", "中", "文", "测", "试", "中文", "文测", "测试"])))

    def test_index_payload_excludes_cache_and_has_recursive_sources(self):
        (self.project / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
        nested = self.project / ".moss-mem/tasks/nested"
        nested.mkdir(parents=True)
        (nested / "one.md").write_text("# One\n", encoding="utf-8")
        cache = self.project / ".moss-mem/index-cache"
        cache.mkdir(parents=True)
        (cache / "memory-index.md").write_text("# cache\n", encoding="utf-8")
        with mock.patch.object(memory_manager, "MEMORY_FILE", str(self.project / "MEMORY.md")), mock.patch.object(memory_manager, "TASKS_DIR", str(self.project / ".moss-mem/tasks")), mock.patch.object(memory_manager, "SUMMARIES_DIR", str(self.project / ".moss-mem/summaries")):
            paths = memory_manager._discover_memory_sources()
        self.assertEqual({p.name for p in paths}, {"MEMORY.md", "one.md"})

    def test_knowledge_index_empty_project_returns_nonzero(self):
        result = self.run_cli("knowledge-index")
        self.assertNotEqual(result.returncode, 0)

    def test_second_replace_failure_restores_json_and_markdown(self):
        cache = self.project / ".moss-mem/index-cache"
        cache.mkdir(parents=True)
        json_path = cache / "memory-index.json"
        md_path = cache / "memory-index.md"
        json_path.write_bytes(b"old-json")
        md_path.write_bytes(b"old-md")
        payload = {"schema_version": 1, "generated_at": "now", "sources": {}, "records": [], "inverted_terms": {}}
        real_replace = os.replace
        calls = 0
        def fail_second(src, dst):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("second replace failed")
            return real_replace(src, dst)
        with mock.patch.object(memory_manager, "INDEX_CACHE_DIR", str(cache)), mock.patch.object(memory_manager.os, "replace", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "second replace failed"):
                memory_manager._write_index_files(payload, [])
        self.assertEqual(json_path.read_bytes(), b"old-json")
        self.assertEqual(md_path.read_bytes(), b"old-md")
