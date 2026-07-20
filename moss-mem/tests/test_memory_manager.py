import importlib.util
import io
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

    def _write_index_fixture(self):
        (self.project / ".moss-mem/tasks/archive/2026").mkdir(parents=True)
        (self.project / ".moss-mem/summaries").mkdir(parents=True)
        (self.project / "MEMORY.md").write_text("# MEMORY.md\n\n## 下一步指令 [Strict]\n- run tests\n", encoding="utf-8")
        (self.project / ".moss-mem/tasks/20260720-100000_task.md").write_text("# Task - Login\n\n## Description\nRepair login\n", encoding="utf-8")
        (self.project / ".moss-mem/tasks/archive/2026/20260719_task.md").write_text("# Compacted Login Task\n\n## Key Decisions\ntoken refresh race\n", encoding="utf-8")
        (self.project / ".moss-mem/summaries/20260720-auth.md").write_text("---\ntopic: auth summary\ncreated: 2026-07-20 10:00\n---\n\n# Harness Summary\n\n## Summary\nUse httpOnly cookie\n", encoding="utf-8")

    def test_memory_search_ranks_archived_key_decision_first(self):
        self._write_index_fixture(); self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        result = self.run_cli("memory-search", "token refresh race", "--limit", "3")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("kind=archived-task", result.stdout); self.assertIn("20260719_task.md", result.stdout)
        self.assertIn("token refresh race", result.stdout)
        self.assertLess(result.stdout.index("20260719_task.md"), result.stdout.find("[2] ") if "[2] " in result.stdout else len(result.stdout))
        self.assertRegex(result.stdout, r"\[1\] score=[1-9][0-9]* kind=archived-task")

    def test_memory_search_rebuild_recheck_failure_falls_back_once(self):
        self._write_index_fixture()
        module_spec = importlib.util.spec_from_file_location("memory_manager_recheck", SCRIPT)
        module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
        output = io.StringIO(); previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(module, "_load_index_payload", side_effect=[FileNotFoundError, {"schema_version": 1, "sources": {}, "records": [], "inverted_terms": {}}]), mock.patch.object(module, "_index_problem", side_effect=OSError("source disappeared")), mock.patch.object(module, "cmd_knowledge_index", return_value=True) as rebuild, mock.patch("sys.stdout", output):
                self.assertEqual(module.cmd_memory_search("httpOnly cookie"), 0)
        finally:
            os.chdir(previous)
        self.assertEqual(rebuild.call_count, 1)
        self.assertIn("[INDEX-FALLBACK]", output.getvalue())

    def test_memory_search_rebuilds_corrupt_json_index(self):
        self._write_index_fixture(); self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        json_path = self.project / ".moss-mem/index-cache/memory-index.json"; json_path.write_text("{broken", encoding="utf-8")
        result = self.run_cli("memory-search", "httpOnly cookie")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout); self.assertIn("Rebuilding local memory index", result.stdout)
        self.assertIn("20260720-auth.md", result.stdout); self.assertTrue(list(json_path.parent.glob("memory-index.json.bak.*"))); json.loads(json_path.read_text(encoding="utf-8"))

    def test_memory_search_rebuilds_non_object_json_index(self):
        self._write_index_fixture(); self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        json_path = self.project / ".moss-mem/index-cache/memory-index.json"; json_path.write_text("[]", encoding="utf-8")
        result = self.run_cli("memory-search", "httpOnly cookie")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Rebuilding local memory index: schema mismatch", result.stdout)
        self.assertIn("20260720-auth.md", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertIsInstance(json.loads(json_path.read_text(encoding="utf-8")), dict)

    def test_memory_search_direct_scans_when_rebuild_fails(self):
        self._write_index_fixture(); spec = importlib.util.spec_from_file_location("memory_manager_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); previous = Path.cwd(); output = io.StringIO()
        try:
            os.chdir(self.project)
            with mock.patch.object(module, "cmd_knowledge_index", return_value=False), mock.patch("sys.stdout", output):
                exit_code = module.cmd_memory_search("httpOnly cookie")
        finally: os.chdir(previous)
        self.assertEqual(exit_code, 0); self.assertIn("[INDEX-FALLBACK]", output.getvalue()); self.assertIn("20260720-auth.md", output.getvalue())

    def test_memory_search_direct_fallback_when_index_write_fails(self):
        self._write_index_fixture(); module_spec = importlib.util.spec_from_file_location("memory_manager_write_fail", SCRIPT)
        module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
        output = io.StringIO(); previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(module, "_write_index_files", side_effect=OSError("disk full")), mock.patch("sys.stdout", output):
                self.assertEqual(module.cmd_memory_search("httpOnly cookie"), 0)
        finally: os.chdir(previous)
        self.assertIn("[INDEX-FALLBACK]", output.getvalue())

    def test_search_edge_cases_and_backup_collision(self):
        self._write_index_fixture(); module = memory_manager
        cache = self.project / ".moss-mem/index-cache"; cache.mkdir(parents=True)
        index = cache / "memory-index.json"; index.write_text("bad", encoding="utf-8")
        with mock.patch.object(module, "INDEX_CACHE_DIR", str(cache)), mock.patch.object(module, "get_timestamp", return_value="fixed"):
            first = module._backup_corrupt_index(); index.write_text("bad2", encoding="utf-8"); second = module._backup_corrupt_index()
        self.assertNotEqual(first, second); self.assertTrue(second.name.endswith("-2"))
        payload = {"records": [{"id": 1, "title": "中文", "sections": {"Summary": "中文测试"}, "preview": "中文测试", "mtime_ns": 1, "path": "x.md", "kind": "memory"}], "inverted_terms": {"中": [1]}}
        self.assertIsInstance(module._search_records(payload, "!!!", 10), list)
        self.assertTrue(module._search_records(payload, "中", 10))
        self.assertTrue(module._search_records(payload, "中文", 10))
        with self.assertRaises(ValueError): module._search_records(payload, "x", 0)

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

    def test_knowledge_check_strict_fails_when_index_is_stale(self):
        self._write_index_fixture()
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        task = self.project / ".moss-mem/tasks/20260720-100000_task.md"
        task.write_text(task.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
        result = self.run_cli("knowledge-check", "--strict")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("memory index is stale", result.stdout)

    def test_knowledge_check_reports_malformed_sources_schema(self):
        self._write_index_fixture()
        (self.project / ".moss-mem/tasks/MEMORY_ARCHIVE.md").write_text("# Archive\n", encoding="utf-8")
        cache = self.project / ".moss-mem/index-cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "memory-index.md").write_text("# Memory Index\n", encoding="utf-8")
        for sources in (None, []):
            with self.subTest(sources=sources):
                payload = {
                    "schema_version": 1,
                    "generated_at": "now",
                    "sources": sources,
                    "records": [],
                    "inverted_terms": {},
                }
                (cache / "memory-index.json").write_text(json.dumps(payload), encoding="utf-8")
                result = self.run_cli("knowledge-check")
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("memory index is stale: schema mismatch", result.stdout)
                self.assertNotIn("Traceback", result.stdout + result.stderr)
                strict = self.run_cli("knowledge-check", "--strict")
                self.assertEqual(strict.returncode, 1, strict.stderr + strict.stdout)
                self.assertIn("memory index is stale: schema mismatch", strict.stdout)
                self.assertNotIn("Traceback", strict.stdout + strict.stderr)

    def test_knowledge_check_rejects_malformed_generated_schema(self):
        self._write_index_fixture(); (self.project / ".moss-mem/tasks/MEMORY_ARCHIVE.md").write_text("# Archive\n", encoding="utf-8"); self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        cache = self.project / ".moss-mem/index-cache"; index_path = cache / "memory-index.json"
        valid = json.loads(index_path.read_text(encoding="utf-8"))
        cases = []
        for value in (None,):
            p = json.loads(json.dumps(valid)); p["records"] = value; cases.append(p)
        p = json.loads(json.dumps(valid)); del p["records"][0]["title"]; cases.append(p)
        p = json.loads(json.dumps(valid)); del p["records"][0]["title"]; p["records"][0]["extra"] = "x"; cases.append(p)
        p = json.loads(json.dumps(valid)); p["inverted_terms"] = []; cases.append(p)
        p = json.loads(json.dumps(valid)); p["inverted_terms"] = {"ghost": [999999]}; cases.append(p)
        for payload in cases:
            index_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.run_cli("knowledge-check", "--strict")
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("schema mismatch", result.stdout); self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_knowledge_check_valid_json_warns_on_invalid_markdown(self):
        self._write_index_fixture(); (self.project / ".moss-mem/tasks/MEMORY_ARCHIVE.md").write_text("# Archive\n", encoding="utf-8"); self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        markdown = self.project / ".moss-mem/index-cache/memory-index.md"
        markdown.write_text("# wrong\nRecords: 0\n", encoding="utf-8")
        normal = self.run_cli("knowledge-check")
        self.assertEqual(normal.returncode, 0, normal.stderr + normal.stdout)
        self.assertIn("memory markdown index is invalid", normal.stdout)
        strict = self.run_cli("knowledge-check", "--strict")
        self.assertEqual(strict.returncode, 1, strict.stderr + strict.stdout)
        self.assertIn("memory markdown index is invalid", strict.stdout)

    def test_memory_search_rebuilds_schema_mismatch_index(self):
        self._write_index_fixture(); self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        index_path = self.project / ".moss-mem/index-cache/memory-index.json"
        payload = json.loads(index_path.read_text(encoding="utf-8")); payload["records"] = None
        index_path.write_text(json.dumps(payload), encoding="utf-8")
        result = self.run_cli("memory-search", "httpOnly cookie")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Rebuilding local memory index: schema mismatch", result.stdout)
        self.assertIn("httpOnly cookie", result.stdout); self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_summary_capture_recommends_local_reindex_only(self):
        result = self.run_cli(
            "summary-capture", "-t", "auth", "-s", "cookie decision",
            "--decisions", "httpOnly cookie", "-n", "run tests",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("knowledge-index", result.stdout)
        removed_name = "mem" + "palace"
        self.assertNotIn(removed_name, result.stdout.lower())
        summary = next((self.project / ".moss-mem/summaries").glob("*.md"))
        self.assertNotIn(removed_name, summary.read_text(encoding="utf-8").lower())

    def test_compaction_recommends_local_reindex_only(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        for index in range(3):
            (tasks / f"20260720-10000{index}_task.md").write_text(
                f"# Task {index}\n\n## Description\nTask {index}\n",
                encoding="utf-8",
            )

        result = self.run_cli("state", "compact", "--keep-recent", "1", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("knowledge-index", result.stdout)
        removed_name = "mem" + "palace"
        self.assertNotIn(removed_name, result.stdout.lower())

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
