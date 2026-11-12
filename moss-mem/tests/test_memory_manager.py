import importlib.util
import io
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "memory_manager.py"
SPEC = importlib.util.spec_from_file_location("memory_manager", SCRIPT)
memory_manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(memory_manager)


def _mrr_at_k(results, relevance, k=3):
    for index, result in enumerate(results[:k], 1):
        if relevance.get(result["memory_id"], 0) > 0:
            return 1.0 / index
    return 0.0


def _ndcg_at_k(results, relevance, k=3):
    gains = [relevance.get(result["memory_id"], 0) for result in results[:k]]
    dcg = sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(gains))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


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
        self.assertIn("20260720-auth.md", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

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

    def test_release_lock_does_not_delete_foreign_token(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        lock = tasks / ".edit_lock"
        lock.write_text(
            json.dumps({"pid": 999999, "token": "foreign", "created_at": "now"}),
            encoding="utf-8",
        )
        with mock.patch.object(memory_manager, "TASKS_DIR", str(tasks)):
            memory_manager._HELD_LOCK_TOKEN = None
            removed = memory_manager.release_lock()
        self.assertFalse(removed)
        self.assertTrue(lock.exists())

    def test_release_lock_removes_owned_token(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        lock = tasks / ".edit_lock"
        lock.write_text(
            json.dumps({"pid": os.getpid(), "token": "owned", "created_at": "now"}),
            encoding="utf-8",
        )
        with mock.patch.object(memory_manager, "TASKS_DIR", str(tasks)):
            memory_manager._HELD_LOCK_TOKEN = "owned"
            removed = memory_manager.release_lock()
            memory_manager._HELD_LOCK_TOKEN = None
        self.assertTrue(removed)
        self.assertFalse(lock.exists())

    def test_release_lock_keeps_replacement_after_claim(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        lock = tasks / ".edit_lock"
        lock.write_text(
            json.dumps({"pid": os.getpid(), "token": "owned", "created_at": "now"}),
            encoding="utf-8",
        )
        real_rename = os.rename

        def replace_after_claim(source, destination):
            result = real_rename(source, destination)
            if Path(source) == lock:
                lock.write_text(
                    json.dumps({"pid": 999999, "token": "replacement", "created_at": "later"}),
                    encoding="utf-8",
                )
            return result

        with mock.patch.object(memory_manager, "TASKS_DIR", str(tasks)), \
                mock.patch.object(memory_manager.os, "rename", side_effect=replace_after_claim):
            memory_manager._HELD_LOCK_TOKEN = "owned"
            removed = memory_manager.release_lock()
            memory_manager._HELD_LOCK_TOKEN = None
        self.assertTrue(removed)
        self.assertTrue(lock.exists())
        self.assertEqual(json.loads(lock.read_text(encoding="utf-8"))["token"], "replacement")

    def test_read_only_cli_does_not_remove_foreign_lock(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        lock = tasks / ".edit_lock"
        lock.write_text(
            json.dumps({"pid": 999999, "token": "foreign", "created_at": "now"}),
            encoding="utf-8",
        )
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(lock.exists())

    def test_mutation_lock_releases_owned_lock_after_exception(self):
        self.assertTrue(hasattr(memory_manager, "mutation_lock"))
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with self.assertRaisesRegex(RuntimeError, "boom"):
                with memory_manager.mutation_lock("unit-test"):
                    self.assertTrue((tasks / ".edit_lock").exists())
                    raise RuntimeError("boom")
        finally:
            os.chdir(previous)
        self.assertFalse((tasks / ".edit_lock").exists())

    def test_same_timestamp_starts_keep_both_task_files(self):
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(memory_manager, "get_timestamp", return_value="20261111-140000"):
                memory_manager.cmd_start("first task", "first next")
                memory_manager.cmd_start("second task", "second next")
        finally:
            os.chdir(previous)
        task_files = list((self.project / ".moss-mem/tasks").glob("*.md"))
        self.assertEqual(len(task_files), 2)
        bodies = {path.read_text(encoding="utf-8") for path in task_files}
        self.assertTrue(any("first task" in body for body in bodies))
        self.assertTrue(any("second task" in body for body in bodies))

    def test_same_timestamp_summary_captures_keep_both_files(self):
        class FixedDateTime:
            @classmethod
            def now(cls):
                return cls()

            def strftime(self, fmt):
                if fmt == "%Y-%m-%d %H:%M":
                    return "2026-11-11 14:00"
                return "20261111-140000"

            def isoformat(self, *args, **kwargs):
                return "2026-11-11T14:00:00"

        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(memory_manager, "datetime", FixedDateTime):
                memory_manager.cmd_summary_capture("same topic", "first summary")
                memory_manager.cmd_summary_capture("same topic", "second summary")
        finally:
            os.chdir(previous)
        summary_files = list((self.project / ".moss-mem/summaries").glob("*.md"))
        self.assertEqual(len(summary_files), 2)
        bodies = {path.read_text(encoding="utf-8") for path in summary_files}
        self.assertTrue(any("first summary" in body for body in bodies))
        self.assertTrue(any("second summary" in body for body in bodies))

    def test_state_notes_append_without_removing_previous_notes(self):
        self.assertEqual(self.run_cli("state", "init").returncode, 0)
        first = self.run_cli("state", "note", "first note")
        second = self.run_cli("state", "note", "second note")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        memory = (self.project / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("first note", memory)
        self.assertIn("second note", memory)

    def test_complete_clears_current_pointer(self):
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            memory_manager.cmd_init()
            memory_manager.cmd_start("finish me", "run tests")
            memory_manager.cmd_complete("finished")
            self.assertIsNone(memory_manager.get_current_task_file())
        finally:
            os.chdir(previous)
        memory = (self.project / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("**当前指针**：`N/A`", memory)

    def test_schema_v2_metadata_normalizes_fields(self):
        path = self.project / "task.md"
        metadata = memory_manager._parse_memory_metadata({
            "schema_version": "2",
            "memory_id": "mem_0123456789abcdef0123456789abcdef",
            "source": "  human:mt  ",
            "trust": "0.900000",
            "recorded_at": "2026-11-12T10:30:00-08:00",
            "valid_from": "2026-11-01T00:00:00Z",
            "valid_to": "2026-12-01T00:00:00+00:00",
            "supersedes": "mem_b; mem_a; mem_b",
        }, path)
        self.assertEqual(metadata["schema_version"], 2)
        self.assertEqual(metadata["memory_id"], "mem_0123456789abcdef0123456789abcdef")
        self.assertEqual(metadata["source"], "human:mt")
        self.assertEqual(metadata["trust"], "0.9")
        self.assertEqual(metadata["recorded_at"], "2026-11-12T18:30:00+00:00")
        self.assertEqual(metadata["valid_from"], "2026-11-01T00:00:00+00:00")
        self.assertEqual(metadata["supersedes"], ["mem_a", "mem_b"])
        self.assertFalse(metadata["legacy"])

    def test_schema_v2_metadata_rejects_invalid_values(self):
        path = self.project / "task.md"
        valid = {
            "schema_version": "2",
            "memory_id": "mem_0123456789abcdef0123456789abcdef",
        }
        invalid = [
            {"source": "bad\nsource"},
            {"trust": "NaN"},
            {"trust": "1e-2"},
            {"trust": "1.0000001"},
            {"recorded_at": "2026-11-12T10:30:00"},
            {"valid_from": "2026-12-01T00:00:00Z", "valid_to": "2026-11-01T00:00:00Z"},
        ]
        for override in invalid:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    memory_manager._parse_memory_metadata({**valid, **override}, path)

    def test_schema_v2_metadata_uses_legacy_shape_and_virtual_id(self):
        path = self.project / "legacy.md"
        metadata = memory_manager._parse_memory_metadata({}, path)
        self.assertEqual(metadata["schema_version"], 1)
        self.assertTrue(metadata["legacy"])
        self.assertTrue(metadata["memory_id"].startswith("legacy:"))
        self.assertEqual(metadata["source"], None)
        self.assertEqual(metadata["trust"], None)
        self.assertEqual(metadata["supersedes"], [])

    def test_schema_v2_memory_id_retries_collision(self):
        first = "0" * 32
        second = "1" * 32
        with mock.patch.object(memory_manager.secrets, "token_hex", side_effect=[first, second]):
            value = memory_manager._new_memory_id({f"mem_{first}"})
        self.assertEqual(value, f"mem_{second}")

    def test_start_writes_schema_v2_metadata_when_explicit(self):
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            memory_manager.cmd_start(
                "v2 task", "next", source="human:mt", trust="0.8",
                valid_from="2026-11-01T00:00:00Z",
            )
        finally:
            os.chdir(previous)
        task = next((self.project / ".moss-mem/tasks").glob("*.md"))
        text = task.read_text(encoding="utf-8")
        self.assertIn("schema_version: 2", text)
        self.assertIn("source: human:mt", text)
        self.assertIn("trust: 0.8", text)
        self.assertIn("valid_from: 2026-11-01T00:00:00+00:00", text)
        self.assertRegex(text, r"memory_id: mem_[0-9a-f]{32}")
        self.assertRegex(text, r"recorded_at: 20[0-9]{2}-[0-9]{2}-[0-9]{2}T")

    def test_summary_capture_writes_schema_v2_metadata(self):
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            memory_manager.cmd_summary_capture(
                "v2 summary", "body", source="agent:codex", trust="1",
                valid_to="2026-12-01T00:00:00Z",
                supersedes="mem_b;mem_a;mem_b",
            )
        finally:
            os.chdir(previous)
        summary = next((self.project / ".moss-mem/summaries").glob("*.md"))
        text = summary.read_text(encoding="utf-8")
        self.assertIn("schema_version: 2", text)
        self.assertIn("source: agent:codex", text)
        self.assertIn("trust: 1.0", text)
        self.assertIn("valid_to: 2026-12-01T00:00:00+00:00", text)
        self.assertIn("supersedes: mem_a;mem_b", text)

    def test_update_promotes_legacy_task_only_with_explicit_metadata(self):
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            tasks = self.project / ".moss-mem/tasks"
            tasks.mkdir(parents=True)
            task = tasks / "legacy.md"
            task.write_text(
                "---\nname: legacy\ncustom: keep-me\ntype: task\n---\n\n"
                "# Legacy\n\n## Description\nold\n\n## Next Step\nnext\n\n"
                "## Last Action\nold\n\n## Key Decisions\nold\n\n## Landmines\nnone\n",
                encoding="utf-8",
            )
            (self.project / "MEMORY.md").write_text(
                "# MEMORY\n\n## 状态机 [Strict]\n- **当前指针**：`%s`\n"
                "- **最后状态**：🔧 In Progress\n\n## 下一步指令 [Strict]\n- next\n"
                % task,
                encoding="utf-8",
            )
            memory_manager.cmd_update(
                "progress", "next", "🔧", source="tool:ci", trust="0.7",
                last_action="updated",
            )
        finally:
            os.chdir(previous)
        text = task.read_text(encoding="utf-8")
        self.assertIn("schema_version: 2", text)
        self.assertIn("custom: keep-me", text)
        self.assertIn("source: tool:ci", text)
        self.assertIn("trust: 0.7", text)
        self.assertRegex(text, r"memory_id: mem_[0-9a-f]{32}")

    def test_index_record_contains_v2_metadata_and_legacy_shape(self):
        v2 = self.project / "v2.md"
        v2.write_text(
            "---\nschema_version: 2\nmemory_id: mem_0123456789abcdef0123456789abcdef\n"
            "source: human:mt\ntrust: 0.9\nrecorded_at: 2026-11-12T10:00:00Z\n---\n\n"
            "# V2\n\n## Summary\nnew\n",
            encoding="utf-8",
        )
        legacy = self.project / "legacy.md"
        legacy.write_text("# Legacy\n\n## Summary\nold\n", encoding="utf-8")
        v2_record = memory_manager._parse_memory_record(v2, 0)
        legacy_record = memory_manager._parse_memory_record(legacy, 1)
        self.assertEqual(v2_record["schema_version"], 2)
        self.assertEqual(v2_record["metadata"]["source"], "human:mt")
        self.assertEqual(legacy_record["schema_version"], 1)
        self.assertTrue(legacy_record["metadata"]["legacy"])
        self.assertIsNone(legacy_record["metadata"]["trust"])

    def test_supersession_graph_supports_multiple_superseders_and_rejects_cycles(self):
        records = [
            {"memory_id": "mem_" + "a" * 32, "metadata": {"supersedes": []}},
            {"memory_id": "mem_" + "b" * 32, "metadata": {"supersedes": ["mem_" + "a" * 32]}},
            {"memory_id": "mem_" + "c" * 32, "metadata": {"supersedes": ["mem_" + "a" * 32]}},
        ]
        graph = memory_manager._build_supersession_graph(records)
        self.assertEqual(graph["mem_" + "a" * 32], ["mem_" + "b" * 32, "mem_" + "c" * 32])
        records[0]["metadata"]["supersedes"] = ["mem_" + "b" * 32]
        with self.assertRaises(ValueError):
            memory_manager._build_supersession_graph(records)

    def test_digest_metadata_marker_round_trips(self):
        marker = (
            '<!-- moss-mem-meta: {"memory_id":"mem_0123456789abcdef0123456789abcdef",'
            '"schema_version":2,"source":"human:mt","trust":"0.9",'
            '"recorded_at":"2026-11-12T10:00:00+00:00","valid_from":null,'
            '"valid_to":null,"supersedes":[]} -->'
        )
        parsed = memory_manager._parse_digest_metadata_marker(marker)
        self.assertEqual(parsed["memory_id"], "mem_0123456789abcdef0123456789abcdef")
        self.assertEqual(parsed["supersedes"], [])

    def test_search_metadata_filters_are_inclusive_and_unknown_safe(self):
        old_id = "mem_" + "a" * 32
        new_id = "mem_" + "b" * 32
        legacy_id = "legacy:" + "c" * 64
        def record(rid, memory_id, trust, valid_from=None, valid_to=None, source="human:mt"):
            metadata = {
                "schema_version": 2 if memory_id.startswith("mem_") else 1,
                "memory_id": memory_id,
                "source": source if memory_id.startswith("mem_") else None,
                "trust": trust,
                "recorded_at": "2026-11-01T00:00:00+00:00" if memory_id.startswith("mem_") else None,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "supersedes": [],
                "legacy": not memory_id.startswith("mem_"),
            }
            return {
                "id": rid, "memory_id": memory_id, "schema_version": metadata["schema_version"],
                "title": "Cookie", "kind": "task", "created": "", "mtime_ns": rid,
                "sections": {"Summary": "cookie policy"}, "preview": "cookie policy",
                "metadata": metadata,
            }
        payload = {
            "records": [
                record(1, old_id, "0.8", "2026-11-01T00:00:00+00:00", "2026-11-15T00:00:00+00:00"),
                record(2, new_id, "0.9", "2026-11-15T00:00:00+00:00"),
                record(3, legacy_id, None),
            ],
            "inverted_terms": {"cookie": [1, 2, 3], "policy": [1, 2, 3]},
            "superseded_by": {old_id: [new_id], new_id: [], legacy_id: []},
        }
        at_boundary = memory_manager._search_records(
            payload, "cookie", 10, source="human:mt", min_trust="0.9",
            as_of="2026-11-15T00:00:00Z", include_superseded=True,
        )
        self.assertEqual([item["memory_id"] for item in at_boundary], [new_id])
        self.assertEqual(
            [item["memory_id"] for item in memory_manager._search_records(payload, "cookie", 10, as_of="2026-11-10T00:00:00Z")],
            [old_id],
        )

    def test_search_explain_includes_relation_context_and_metadata(self):
        old_id = "mem_" + "a" * 32
        new_id = "mem_" + "b" * 32
        base = {
            "schema_version": 2, "source": "human:mt", "trust": "0.9",
            "recorded_at": "2026-11-01T00:00:00+00:00", "valid_from": None,
            "valid_to": None, "legacy": False,
        }
        old = {"id": 1, "memory_id": old_id, "schema_version": 2, "title": "Old", "kind": "task", "created": "", "mtime_ns": 1, "sections": {"Summary": "cookie"}, "preview": "cookie", "metadata": {**base, "memory_id": old_id, "supersedes": []}}
        new = {"id": 2, "memory_id": new_id, "schema_version": 2, "title": "New", "kind": "task", "created": "", "mtime_ns": 2, "sections": {"Summary": "cookie"}, "preview": "cookie", "metadata": {**base, "memory_id": new_id, "supersedes": [old_id]}}
        payload = {"records": [old, new], "inverted_terms": {"cookie": [1, 2]}, "superseded_by": {old_id: [new_id], new_id: []}}
        results = memory_manager._search_records(payload, "cookie", 10)
        self.assertEqual(results[0]["memory_id"], new_id)
        old_result = next(item for item in results if item["memory_id"] == old_id)
        self.assertEqual(old_result["superseded_by"], [new_id])
        self.assertEqual(memory_manager._supersession_chain(payload, new_id, "supersedes"), [old_id])

    def test_retrieval_field_map_concatenates_sections_and_buckets_unknowns(self):
        record = {
            "title": "Cookie Policy",
            "sections": {
                "Summary": ["first cookie", "second policy"],
                "Key Decisions": "choose secure cookie",
                "Scratch": "opaque note",
            },
        }
        fields = memory_manager._canonical_retrieval_fields(record)
        self.assertEqual(list(fields), ["title", "Summary", "Key Decisions", "__other__"])
        self.assertEqual(fields["title"], ["cookie", "policy"])
        self.assertEqual(fields["Summary"], ["first", "cookie", "second", "policy"])
        self.assertEqual(fields["__other__"], ["opaque", "note"])
        self.assertEqual(memory_manager._RETRIEVAL_FIELD_BOOSTS["title"], 3.0)

    def test_search_golden_fixture_has_fixed_queries_and_expected_orders(self):
        fixture = Path(__file__).parent / "fixtures" / "search-golden.json"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data), 20)
        for case in data:
            self.assertIn("query", case)
            self.assertIn("relevance", case)
            self.assertIn("expected_bm25_top", case)
            self.assertIn("expected_legacy_top", case)
            self.assertTrue(all(isinstance(value, int) and 0 <= value <= 2 for value in case["relevance"].values()))

    def test_search_golden_corpus_matches_bm25_and_legacy_orders(self):
        fixture = json.loads((Path(__file__).parent / "fixtures" / "search-golden.json").read_text(encoding="utf-8"))
        records = []
        for index, case in enumerate(fixture, 1):
            memory_id = next(iter(case["relevance"]))
            metadata = {"schema_version": 2, "memory_id": memory_id, "source": "golden", "trust": "0.5", "recorded_at": "2026-11-01T00:00:00+00:00", "valid_from": None, "valid_to": None, "supersedes": [], "legacy": False}
            records.append({"id": index, "memory_id": memory_id, "schema_version": 2, "path": f"golden/{index}.md", "kind": "task", "title": case["query"], "created": "", "mtime_ns": index, "sections": {"Summary": case["query"]}, "preview": case["query"], "metadata": metadata})
        distractor_metadata = {"schema_version": 2, "memory_id": "mem_ffffffffffffffffffffffffffffffff", "source": "golden", "trust": "0.5", "recorded_at": "2026-11-01T00:00:00+00:00", "valid_from": None, "valid_to": None, "supersedes": [], "legacy": False}
        records.extend([
            {"id": 1001, "memory_id": "mem_ffffffffffffffffffffffffffffffff", "schema_version": 2, "path": "golden/distractor-summary.md", "kind": "summary", "title": "Archive note", "created": "", "mtime_ns": 1001, "sections": {"Summary": "cookie policy " + ("historical noise " * 40)}, "preview": "cookie policy", "metadata": distractor_metadata},
            {"id": 1002, "memory_id": "mem_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "schema_version": 2, "path": "golden/distractor-title.md", "kind": "task", "title": "Cookie", "created": "", "mtime_ns": 1002, "sections": {"Summary": "policy " + ("old note " * 40)}, "preview": "policy", "metadata": {**distractor_metadata, "memory_id": "mem_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"}},
        ])
        inverted = {}
        for record in records:
            for term in set(memory_manager._tokenize(record["title"] + " " + record["sections"]["Summary"])):
                inverted.setdefault(term, []).append(record["id"])
        payload = {"records": records, "inverted_terms": inverted, "superseded_by": {record["memory_id"]: [] for record in records}}
        payload["retrieval_stats"] = memory_manager._build_retrieval_stats(records, inverted)
        mrr_values, ndcg_values = [], []
        for case in fixture:
            bm25 = memory_manager._search_records(payload, case["query"], 3, rank="bm25f")
            legacy = memory_manager._search_records(payload, case["query"], 3, rank="legacy")
            self.assertEqual([item["memory_id"] for item in bm25[:len(case["expected_bm25_top"])]], case["expected_bm25_top"])
            self.assertEqual([item["memory_id"] for item in legacy[:len(case["expected_legacy_top"])]], case["expected_legacy_top"])
            mrr_values.append(_mrr_at_k(bm25, case["relevance"]))
            ndcg_values.append(_ndcg_at_k(bm25, case["relevance"]))
        self.assertGreaterEqual(sum(mrr_values) / len(mrr_values), 0.95)
        self.assertGreaterEqual(sum(ndcg_values) / len(ndcg_values), 0.95)

    def test_skill_documents_rank_modes_and_schema3_stats(self):
        skill = (Path(__file__).parents[1] / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--rank", skill)
        self.assertIn("retrieval_stats", skill)

    def test_retrieval_stats_schema3_has_integer_lengths_and_fingerprint(self):
        records = [
            {"title": "Cookie", "sections": {"Summary": "cookie policy"}, "id": 1},
            {"title": "", "sections": {}, "id": 2},
        ]
        inverted = {"cookie": [1], "policy": [1]}
        stats = memory_manager._build_retrieval_stats(records, inverted)
        self.assertEqual(stats["scorer"], "bm25f-v1")
        self.assertEqual(stats["doc_count"], 2)
        self.assertIsInstance(stats["fields"]["title"]["avg_len_milli"], int)
        self.assertEqual(stats["doc_freq"], {"cookie": 1, "policy": 1})
        self.assertRegex(stats["stats_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            stats["stats_fingerprint"],
            memory_manager._retrieval_stats_fingerprint({k: v for k, v in stats.items() if k != "stats_fingerprint"}),
        )

    def test_index_payload_writes_and_validates_dual_schema3_versions(self):
        self._write_index_fixture()
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            payload, _ = memory_manager._build_index_payload()
            self.assertIsNone(memory_manager._index_problem(payload))
            payload["index_schema_version"] = 2
            self.assertIn("schema", memory_manager._index_problem(payload))
            payload["index_schema_version"] = 3
        finally:
            os.chdir(previous)
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["index_schema_version"], 3)

    def test_schema2_payload_is_reported_as_stale_for_rebuild(self):
        payload = {"schema_version": 2, "sources": {}, "records": [], "inverted_terms": {}}
        self.assertIn("schema", memory_manager._index_problem(payload))

    def test_bm25f_scoring_uses_idf_length_norm_phrase_and_quantization(self):
        records = [
            {"id": 1, "title": "cookie policy", "sections": {"Summary": "cookie cookie"}, "preview": ""},
            {"id": 2, "title": "other", "sections": {"Summary": "cookie"}, "preview": ""},
        ]
        inverted = {"cookie": [1, 2], "policy": [1]}
        stats = memory_manager._build_retrieval_stats(records, inverted)
        scored = memory_manager._bm25f_score_record(records[0], ["cookie", "policy"], stats)
        self.assertGreater(scored["score_raw"], 0)
        self.assertEqual(scored["score_milli"], int(scored["score_raw"] * 1000 + 0.5))
        self.assertEqual(scored["phrase_bonus"], 0.25 * min(max(scored["term_score_sum"], 1), 8))
        self.assertTrue(all("field" in item and "idf" in item for item in scored["contributions"]))
        expected_idf = __import__("math").log1p((2 - 2 + 0.5) / (2 + 0.5))
        self.assertAlmostEqual(scored["contributions"][0]["idf"], expected_idf, places=6)

    def test_bm25f_requires_all_query_terms_for_phrase_bonus_and_legacy_rank(self):
        record = {"id": 1, "memory_id": "legacy:x", "title": "cookie", "kind": "task", "created": "", "mtime_ns": 1, "sections": {"Summary": "policy"}, "preview": "cookie policy", "metadata": {"schema_version": 1, "memory_id": "legacy:x", "source": None, "trust": None, "recorded_at": None, "valid_from": None, "valid_to": None, "supersedes": [], "legacy": True}}
        stats = memory_manager._build_retrieval_stats([record], {"cookie": [1], "policy": [1]})
        partial = memory_manager._bm25f_score_record(record, ["cookie", "missing"], stats)
        self.assertEqual(partial["phrase_bonus"], 0)
        payload = {"records": [record], "inverted_terms": {"cookie": [1], "policy": [1]}, "superseded_by": {"legacy:x": []}, "retrieval_stats": stats}
        legacy = memory_manager._search_records(payload, "cookie", 10, rank="legacy")
        self.assertEqual(len(legacy), 1)

    def test_memory_search_help_exposes_schema_v2_filters(self):
        result = self.run_cli("memory-search", "--help")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for flag in ("--source", "--min-trust", "--as-of", "--include-superseded", "--explain"):
            self.assertIn(flag, result.stdout)

    def test_memory_search_rank_modes_and_bm25_explain_output(self):
        self._write_index_fixture()
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        bm25 = self.run_cli("memory-search", "token refresh race", "--explain")
        self.assertEqual(bm25.returncode, 0, bm25.stderr + bm25.stdout)
        self.assertIn("scorer=bm25f-v1", bm25.stdout)
        self.assertIn("term=token", bm25.stdout)
        self.assertIn("phrase_bonus=", bm25.stdout)
        self.assertIn("final_tiebreak=", bm25.stdout)
        partial = self.run_cli("memory-search", "token absent-term", "--explain")
        self.assertEqual(partial.returncode, 0, partial.stderr + partial.stdout)
        self.assertIn("term=absent field=none tf=0", partial.stdout)
        legacy = self.run_cli("memory-search", "token refresh race", "--rank", "legacy", "--explain")
        self.assertEqual(legacy.returncode, 0, legacy.stderr + legacy.stdout)
        self.assertIn("scorer=legacy-v1", legacy.stdout)
        invalid = self.run_cli("memory-search", "token", "--rank", "invalid")
        self.assertNotEqual(invalid.returncode, 0)

    def test_bm25_explain_reports_active_validity_tiebreak(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        (self.project / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
        (self.project / ".moss-mem/tasks/MEMORY_ARCHIVE.md").write_text("# Archive\n", encoding="utf-8")
        (tasks / "active.md").write_text(
            "---\nschema_version: 2\nmemory_id: mem_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
            "recorded_at: 2026-11-01T00:00:00Z\nvalid_from: 2026-11-01T00:00:00Z\n"
            "valid_to: 2026-12-01T00:00:00Z\n---\n# Active\n\n## Summary\nneedle\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        result = self.run_cli("memory-search", "needle", "--as-of", "2026-11-15T00:00:00Z", "--explain")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("final_tiebreak=validity:active", result.stdout)

    def test_section_named_title_is_retained_as_other_retrieval_text(self):
        fields = memory_manager._canonical_retrieval_fields({"title": "Frontmatter", "sections": {"title": "section needle"}})
        self.assertEqual(fields["title"], ["frontmatter"])
        self.assertEqual(fields["__other__"], ["section", "needle"])

    def test_compact_summary_preserves_v2_metadata_marker(self):
        source = self._write_summary(
            "20260101-100000-v2.md",
            "---\nschema_version: 2\n"
            "memory_id: mem_0123456789abcdef0123456789abcdef\n"
            "source: human:mt\ntrust: 0.9\nrecorded_at: 2026-11-12T10:00:00Z\n"
            "---\n\n# Summary\n\n## Summary\nbody\n",
        )
        self._write_summary(
            "20260720-100000-recent.md",
            "---\ntopic: recent\n---\n\n# Summary\n\n## Summary\nrecent\n",
            mtime=1_800_000_000,
        )
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            result = memory_manager.cmd_compact(scope="summaries", keep_recent=1, yes=True)
        finally:
            os.chdir(previous)
        self.assertEqual(result, 0)
        digest = self.project / ".moss-mem/summaries/digest-2026-01.md"
        text = digest.read_text(encoding="utf-8")
        self.assertIn("moss-mem-meta:", text)
        self.assertIn("mem_0123456789abcdef0123456789abcdef", text)
        self.assertFalse(source.exists())

    def test_multi_topic_digest_indexes_each_v2_metadata_marker(self):
        digest = self.project / ".moss-mem/summaries/digest-2026-01.md"
        digest.parent.mkdir(parents=True)
        digest.write_text(
            "# Summary Digest 2026-01\n\n"
            "### first (`one.md`)\n**Summary:** alpha cookie\n"
            "<!-- moss-mem-meta: {\"memory_id\":\"mem_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"schema_version\":2,\"source\":\"one\",\"trust\":0.8,\"recorded_at\":\"2026-01-01T00:00:00+00:00\",\"valid_from\":null,\"valid_to\":null,\"supersedes\":[]} -->\n\n"
            "### second (`two.md`)\n**Summary:** beta cookie\n"
            "<!-- moss-mem-meta: {\"memory_id\":\"mem_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\",\"schema_version\":2,\"source\":\"two\",\"trust\":0.9,\"recorded_at\":\"2026-01-02T00:00:00+00:00\",\"valid_from\":null,\"valid_to\":null,\"supersedes\":[]} -->\n",
            encoding="utf-8",
        )
        (self.project / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            payload, _ = memory_manager._build_index_payload()
        finally:
            os.chdir(previous)
        digest_records = [record for record in payload["records"] if record["path"] == str(digest.relative_to(self.project))]
        self.assertEqual({record["memory_id"] for record in digest_records}, {"mem_" + "a" * 32, "mem_" + "b" * 32})

    def test_index_rejects_duplicate_v2_memory_ids(self):
        tasks = self.project / ".moss-mem/tasks"
        tasks.mkdir(parents=True)
        first = tasks / "first.md"
        second = tasks / "second.md"
        header = (
            "---\nschema_version: 2\nmemory_id: mem_0123456789abcdef0123456789abcdef\n"
            "recorded_at: 2026-11-12T10:00:00Z\n---\n\n"
        )
        first.write_text(header + "# First\n", encoding="utf-8")
        second.write_text(header + "# Second\n", encoding="utf-8")
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with self.assertRaises(ValueError):
                memory_manager._build_index_payload()
        finally:
            os.chdir(previous)

    def test_all_writer_commands_use_shared_mutation_lock(self):
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            memory_manager.cmd_init()
            with mock.patch.object(memory_manager, "mutation_lock", wraps=memory_manager.mutation_lock) as lock:
                memory_manager.cmd_start("writer task", "writer next")
            self.assertEqual(lock.call_count, 1)

            with mock.patch.object(memory_manager, "mutation_lock", wraps=memory_manager.mutation_lock) as lock:
                memory_manager.cmd_summary_capture("writer summary", "summary body")
            self.assertEqual(lock.call_count, 1)

            with mock.patch.object(memory_manager, "mutation_lock", wraps=memory_manager.mutation_lock) as lock:
                self.assertEqual(memory_manager.cmd_compact(dry_run=True, yes=True), 0)
            self.assertEqual(lock.call_count, 1)

            with mock.patch.object(memory_manager, "mutation_lock", wraps=memory_manager.mutation_lock) as lock:
                self.assertTrue(memory_manager.cmd_knowledge_index())
            self.assertEqual(lock.call_count, 1)
        finally:
            os.chdir(previous)

    def test_locked_mutation_preserves_runtime_error_from_command_body(self):
        @memory_manager.locked_mutation("body-error")
        def fail_in_body():
            raise RuntimeError("body boom")

        with self.assertRaisesRegex(RuntimeError, "body boom"):
            fail_in_body()

    def test_read_only_show_does_not_use_mutation_lock(self):
        task = self.project / ".moss-mem/tasks/current_task.md"
        task.parent.mkdir(parents=True)
        task.write_text("# Current\n\n## Description\nread only\n", encoding="utf-8")
        (self.project / "MEMORY.md").write_text(
            "# MEMORY\n\n## 状态机 [Strict]\n- **当前指针**：`%s`\n" % task,
            encoding="utf-8",
        )
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(memory_manager, "mutation_lock", wraps=memory_manager.mutation_lock) as lock:
                memory_manager.cmd_show()
            self.assertEqual(lock.call_count, 0)
        finally:
            os.chdir(previous)

    def _write_summary(self, name, body, mtime=1_700_000_000):
        summaries = self.project / ".moss-mem/summaries"
        summaries.mkdir(parents=True, exist_ok=True)
        path = summaries / name
        path.write_text(body, encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return path

    def test_compact_keeps_unreadable_summary_source(self):
        old = self._write_summary(
            "20260101-100000-bad.md",
            "---\ntopic: bad\n---\n\n# Summary\n\n## Summary\nbad\n",
        )
        self._write_summary(
            "20260102-100000-good.md",
            "---\ntopic: good\n---\n\n# Summary\n\n## Summary\ngood\n",
        )
        self._write_summary(
            "20260720-100000-recent.md",
            "---\ntopic: recent\n---\n\n# Summary\n\n## Summary\nrecent\n",
            mtime=1_800_000_000,
        )
        real_read_text = Path.read_text

        def read_text(path, *args, **kwargs):
            if path.resolve() == old.resolve():
                raise OSError("unreadable source")
            return real_read_text(path, *args, **kwargs)

        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(Path, "read_text", autospec=True, side_effect=read_text):
                result = memory_manager.cmd_compact(scope="summaries", keep_recent=1, yes=True)
        finally:
            os.chdir(previous)
        self.assertEqual(result, 0)
        self.assertTrue(old.exists())

    def test_compact_digest_does_not_duplicate_source_marker_after_delete_failure(self):
        source = self._write_summary(
            "20260101-100000-topic.md",
            "---\ntopic: topic\n---\n\n# Summary\n\n## Summary\nbody\n",
        )
        self._write_summary(
            "20260720-100000-recent.md",
            "---\ntopic: recent\n---\n\n# Summary\n\n## Summary\nrecent\n",
            mtime=1_800_000_000,
        )
        real_unlink = Path.unlink
        failed_once = {"value": False}

        def fail_source_unlink(path, *args, **kwargs):
            if path.resolve() == source.resolve() and not failed_once["value"]:
                failed_once["value"] = True
                raise OSError("keep source for recovery")
            return real_unlink(path, *args, **kwargs)

        source_hash = memory_manager._sha256_path(source)
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(Path, "unlink", autospec=True, side_effect=fail_source_unlink):
                first = memory_manager.cmd_compact(scope="summaries", keep_recent=1, yes=True)
            second = memory_manager.cmd_compact(scope="summaries", keep_recent=1, yes=True)
        finally:
            os.chdir(previous)
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        digest = self.project / ".moss-mem/summaries/digest-2026-01.md"
        marker = f"sha256={source_hash}"
        self.assertEqual(digest.read_text(encoding="utf-8").count(marker), 1)
        self.assertFalse(source.exists())

    def test_compact_source_delete_failure_leaves_manifest(self):
        source = self._write_summary(
            "20260101-100000-topic.md",
            "---\ntopic: topic\n---\n\n# Summary\n\n## Summary\nbody\n",
        )
        self._write_summary(
            "20260720-100000-recent.md",
            "---\ntopic: recent\n---\n\n# Summary\n\n## Summary\nrecent\n",
            mtime=1_800_000_000,
        )
        real_unlink = Path.unlink

        def fail_source_unlink(path, *args, **kwargs):
            if path.resolve() == source.resolve():
                raise OSError("leave manifest")
            return real_unlink(path, *args, **kwargs)

        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(Path, "unlink", autospec=True, side_effect=fail_source_unlink):
                result = memory_manager.cmd_compact(scope="summaries", keep_recent=1, yes=True)
        finally:
            os.chdir(previous)
        self.assertEqual(result, 1)
        manifests = list((self.project / ".moss-mem/transactions").glob("*.json"))
        self.assertTrue(manifests)
        self.assertTrue(source.exists())

    def test_compact_refuses_unreadable_existing_digest(self):
        source = self._write_summary(
            "20260101-100000-topic.md",
            "---\ntopic: topic\n---\n\n# Summary\n\n## Summary\nbody\n",
        )
        self._write_summary(
            "20260720-100000-recent.md",
            "---\ntopic: recent\n---\n\n# Summary\n\n## Summary\nrecent\n",
            mtime=1_800_000_000,
        )
        digest = self.project / ".moss-mem/summaries/digest-2026-01.md"
        digest.parent.mkdir(parents=True, exist_ok=True)
        digest.write_text("existing digest\n", encoding="utf-8")
        original = digest.read_bytes()
        real_read_text = Path.read_text

        def fail_digest_read(path, *args, **kwargs):
            if path.resolve() == digest.resolve():
                raise OSError("digest temporarily unreadable")
            return real_read_text(path, *args, **kwargs)

        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(Path, "read_text", autospec=True, side_effect=fail_digest_read):
                result = memory_manager.cmd_compact(scope="summaries", keep_recent=1, yes=True)
        finally:
            os.chdir(previous)
        self.assertEqual(result, 1)
        self.assertTrue(source.exists())
        self.assertEqual(digest.read_bytes(), original)

    def test_compact_keeps_source_when_changed_after_digest_write(self):
        source = self._write_summary(
            "20260101-100000-topic.md",
            "---\ntopic: topic\n---\n\n# Summary\n\n## Summary\nbody\n",
        )
        self._write_summary(
            "20260720-100000-recent.md",
            "---\ntopic: recent\n---\n\n# Summary\n\n## Summary\nrecent\n",
            mtime=1_800_000_000,
        )
        real_update = memory_manager._manifest_update_entry
        mutated = {"value": False}

        def mutate_after_write(manifest_path, manifest, entry, **updates):
            result = real_update(manifest_path, manifest, entry, **updates)
            if updates.get("status") == "written" and not mutated["value"]:
                mutated["value"] = True
                source.write_text(source.read_text(encoding="utf-8") + "external edit\n", encoding="utf-8")
            return result

        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(memory_manager, "_manifest_update_entry", side_effect=mutate_after_write):
                result = memory_manager.cmd_compact(scope="summaries", keep_recent=1, yes=True)
        finally:
            os.chdir(previous)
        self.assertEqual(result, 1)
        self.assertTrue(source.exists())
        self.assertTrue(list((self.project / ".moss-mem/transactions").glob("*.json")))

    def test_recover_compact_manifest_removes_matching_source(self):
        source = self._write_summary("source.md", "source body\n")
        destination = self.project / ".moss-mem/summaries/digest-2026-01.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            f"<!-- moss-mem-source: {source} sha256={memory_manager._sha256_path(source)} -->\n",
            encoding="utf-8",
        )
        tx_dir = self.project / ".moss-mem/transactions"
        tx_dir.mkdir(parents=True, exist_ok=True)
        manifest = tx_dir / "compact-recover.json"
        manifest.write_text(json.dumps({
            "id": "compact-recover",
            "entries": [{
                "source": str(source),
                "destination": str(destination),
                "source_sha256": memory_manager._sha256_path(source),
                "marker": f"<!-- moss-mem-source: {source} sha256={memory_manager._sha256_path(source)} -->",
                "operation": "summary",
                "status": "written",
            }],
        }), encoding="utf-8")
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            memory_manager.cmd_recover()
        finally:
            os.chdir(previous)
        self.assertFalse(source.exists())
        self.assertFalse(manifest.exists())

    def test_recover_compact_manifest_preserves_hash_conflict(self):
        source = self._write_summary("source.md", "source body\n")
        destination = self.project / ".moss-mem/summaries/digest-2026-01.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("conflicting destination\n", encoding="utf-8")
        tx_dir = self.project / ".moss-mem/transactions"
        tx_dir.mkdir(parents=True, exist_ok=True)
        manifest = tx_dir / "compact-conflict.json"
        manifest.write_text(json.dumps({
            "id": "compact-conflict",
            "entries": [{
                "source": str(source),
                "destination": str(destination),
                "source_sha256": memory_manager._sha256_path(source),
                "marker": "<!-- missing marker -->",
                "operation": "summary",
                "status": "written",
            }],
        }), encoding="utf-8")
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            memory_manager.cmd_recover()
        finally:
            os.chdir(previous)
        self.assertTrue(source.exists())
        self.assertTrue(destination.exists())
        self.assertTrue(manifest.exists())

    def test_recover_rewrite_manifest_requires_verified_destination(self):
        source = self._write_summary("archive.md", "original body\n")
        tx_dir = self.project / ".moss-mem/transactions"
        tx_dir.mkdir(parents=True, exist_ok=True)
        manifest = tx_dir / "rewrite-planned.json"
        manifest.write_text(json.dumps({
            "id": "rewrite-planned",
            "entries": [{
                "source": str(source),
                "destination": str(source),
                "source_sha256": memory_manager._sha256_path(source),
                "operation": "rewrite",
                "status": "planned",
            }],
        }), encoding="utf-8")
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            memory_manager.cmd_recover()
        finally:
            os.chdir(previous)
        self.assertTrue(source.exists())
        self.assertTrue(manifest.exists())

    def test_compact_scope_all_stops_after_failed_scope(self):
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(memory_manager, "_compact_active_tasks", return_value=(1, 0, 0)) as tasks, \
                    mock.patch.object(memory_manager, "_compact_archive", return_value=(0, 0, 0)) as archive, \
                    mock.patch.object(memory_manager, "_compact_summaries", return_value=(0, 0, 0)) as summaries:
                result = memory_manager.cmd_compact(scope="all", keep_recent=1, yes=True)
        finally:
            os.chdir(previous)
        self.assertEqual(result, 1)
        self.assertEqual(tasks.call_count, 1)
        self.assertEqual(archive.call_count, 0)
        self.assertEqual(summaries.call_count, 0)

    def test_index_json_and_markdown_share_build_id(self):
        self._write_index_fixture()
        result = self.run_cli("knowledge-index")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(
            (self.project / ".moss-mem/index-cache/memory-index.json").read_text(encoding="utf-8")
        )
        markdown = (self.project / ".moss-mem/index-cache/memory-index.md").read_text(encoding="utf-8")
        self.assertTrue(payload["build_id"])
        self.assertIn(f"Build ID: {payload['build_id']}", markdown)

    def test_index_problem_rejects_missing_inverted_token(self):
        self._write_index_fixture()
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            payload = memory_manager._load_index_payload()
            term = next(iter(payload["inverted_terms"]))
            del payload["inverted_terms"][term]
            self.assertIsNotNone(memory_manager._index_problem(payload))
        finally:
            os.chdir(previous)

    def test_index_problem_rejects_inverted_reference_without_term_match(self):
        self._write_index_fixture()
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            payload = memory_manager._load_index_payload()
            record_id = payload["records"][0]["id"]
            payload["inverted_terms"]["injected-term"] = [record_id]
            self.assertIn("inverted", memory_manager._index_problem(payload))
        finally:
            os.chdir(previous)

    def test_index_build_retries_when_source_metadata_changes(self):
        self._write_index_fixture()
        previous = Path.cwd()
        try:
            os.chdir(self.project)
            actual = memory_manager._current_source_metadata()
            changed = dict(actual)
            first_path = next(iter(changed))
            changed[first_path] += 1
            with mock.patch.object(
                memory_manager,
                "_current_source_metadata",
                side_effect=[actual, changed, changed, changed],
            ) as metadata:
                payload, warnings = memory_manager._build_index_payload()
            self.assertTrue(payload["records"])
            self.assertEqual(metadata.call_count, 4)
        finally:
            os.chdir(previous)

    def test_concurrent_index_writers_use_distinct_temp_paths(self):
        cache = self.project / ".moss-mem/index-cache"
        cache.mkdir(parents=True)
        payload = {
            "schema_version": 1,
            "generated_at": "now",
            "build_id": "build",
            "sources": {},
            "records": [],
            "inverted_terms": {},
        }
        barrier = threading.Barrier(2)
        real_replace = os.replace
        calls = {"count": 0}
        call_lock = threading.Lock()

        def replace_with_overlap(src, dst):
            with call_lock:
                calls["count"] += 1
                current = calls["count"]
            if current <= 2:
                barrier.wait(timeout=5)
            return real_replace(src, dst)

        def write_index():
            return memory_manager._write_index_files(payload, [])

        previous = Path.cwd()
        try:
            os.chdir(self.project)
            with mock.patch.object(memory_manager, "INDEX_CACHE_DIR", str(cache)), \
                    mock.patch.object(memory_manager.os, "replace", side_effect=replace_with_overlap):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = [pool.submit(write_index) for _ in range(2)]
                    for future in results:
                        future.result()
        finally:
            os.chdir(previous)
        self.assertTrue((cache / "memory-index.json").exists())
        self.assertTrue((cache / "memory-index.md").exists())

    def test_show_reports_stale_pointer_with_next_action(self):
        stale = ".moss-mem/tasks/missing-task.md"
        (self.project / "MEMORY.md").write_text(
            "# MEMORY\n\n## 状态机 [Strict]\n- **当前指针**：`%s`\n" % stale,
            encoding="utf-8",
        )
        result = self.run_cli("show")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale", (result.stdout + result.stderr).lower())
        self.assertIn(stale, result.stdout + result.stderr)
        self.assertIn("state commit", result.stdout + result.stderr)

    def test_knowledge_check_strict_rejects_stale_pointer(self):
        stale = ".moss-mem/tasks/missing-task.md"
        (self.project / "MEMORY.md").write_text(
            "# MEMORY\n\n## 状态机 [Strict]\n- **当前指针**：`%s`\n" % stale,
            encoding="utf-8",
        )
        result = self.run_cli("knowledge-check", "--strict")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale task pointer", result.stdout.lower())
        self.assertIn(stale, result.stdout)

    def test_recover_reports_legacy_lock_stale_pointer_and_pending_manifest(self):
        stale = ".moss-mem/tasks/missing-task.md"
        (self.project / "MEMORY.md").write_text(
            "# MEMORY\n\n## 状态机 [Strict]\n- **当前指针**：`%s`\n" % stale,
            encoding="utf-8",
        )
        lock = self.project / ".moss-mem/tasks/.edit_lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 999999, "time": "old"}), encoding="utf-8")
        manifest = self.project / ".moss-mem/transactions/pending.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"id": "pending", "entries": []}), encoding="utf-8")
        result = self.run_cli("recover")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        output = result.stdout
        self.assertIn(".edit_lock", output)
        self.assertIn("rm ", output)
        self.assertIn("stale pointer", output.lower())
        self.assertIn(stale, output)
        self.assertIn("pending.json", output)
        self.assertTrue(lock.exists())
        self.assertTrue(manifest.exists())

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
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["index_schema_version"], 3)
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

    def test_compact_scope_archive_resummarizes_old_bodies(self):
        archive = self.project / ".moss-mem/tasks/archive/2026"
        archive.mkdir(parents=True)
        # Newest keep-recent=1 left alone; older full-body archive gets re-summarized.
        old = archive / "20260101-old_task.md"
        old.write_text(
            "# Full Archive Body\n\n## Description\nLogin repair\n\n"
            "## Key Decisions\ntoken refresh race\n\n"
            "## Landmines\nnone\n\n"
            "## Scratch Notes\n" + ("noise " * 400) + "\n",
            encoding="utf-8",
        )
        new = archive / "20260720-new_task.md"
        new.write_text(
            "# Compacted from recent\n\n## Key Decisions\nkeep me recent\n",
            encoding="utf-8",
        )
        # Ensure mtime order: new is newer
        os.utime(old, (1_700_000_000, 1_700_000_000))
        os.utime(new, (1_800_000_000, 1_800_000_000))

        result = self.run_cli(
            "state", "compact", "--scope", "archive",
            "--keep-recent", "1", "--yes",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        body = old.read_text(encoding="utf-8")
        self.assertIn("token refresh race", body)
        self.assertIn("# Compacted from", body)
        self.assertNotIn("noise noise", body)
        self.assertIn("keep me recent", new.read_text(encoding="utf-8"))

    def test_compact_scope_summaries_merges_into_monthly_digest(self):
        summaries = self.project / ".moss-mem/summaries"
        summaries.mkdir(parents=True)
        # 3 old + 1 recent; keep-recent=1 → merge 3 into digest
        for idx, day in enumerate(("01", "02", "03")):
            (summaries / f"202601{day}-10000{idx}-topic.md").write_text(
                "---\ntopic: auth topic\ncreated: 2026-01-0%s 10:00\n---\n\n"
                "# Harness Summary\n\n## Summary\nsession %s\n\n"
                "## Decisions\nhttpOnly cookie\n\n## Next Step\nship\n"
                % (day, day),
                encoding="utf-8",
            )
        recent = summaries / "20260720-999999-recent.md"
        recent.write_text(
            "---\ntopic: recent\ncreated: 2026-07-20 10:00\n---\n\n"
            "# Harness Summary\n\n## Summary\nkeep recent\n\n"
            "## Decisions\nrecent decision\n",
            encoding="utf-8",
        )
        # mtimes: recent newest
        for p in summaries.glob("202601*.md"):
            os.utime(p, (1_700_000_000, 1_700_000_000))
        os.utime(recent, (1_800_000_000, 1_800_000_000))

        result = self.run_cli(
            "state", "compact", "--scope", "summaries",
            "--keep-recent", "1", "--yes",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        digest = summaries / "digest-2026-01.md"
        self.assertTrue(digest.exists(), result.stdout)
        digest_text = digest.read_text(encoding="utf-8")
        self.assertIn("httpOnly cookie", digest_text)
        self.assertTrue(recent.exists())
        self.assertEqual(len(list(summaries.glob("202601*.md"))), 0)

        # Search still finds decision after reindex
        (self.project / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        search = self.run_cli("memory-search", "httpOnly cookie")
        self.assertEqual(search.returncode, 0, search.stderr + search.stdout)
        self.assertIn("httpOnly cookie", search.stdout)

    def test_summary_capture_nudge_when_summaries_exceed_threshold(self):
        summaries = self.project / ".moss-mem/summaries"
        summaries.mkdir(parents=True)
        # Create SUMMARY_FILE_THRESHOLD + 1 existing files so capture tips over.
        limit = memory_manager.SUMMARY_FILE_THRESHOLD
        for i in range(limit):
            (summaries / f"20260701-{i:04d}-old.md").write_text(
                f"# old {i}\n\n## Summary\nx\n", encoding="utf-8"
            )
        result = self.run_cli(
            "summary-capture", "-t", "overflow", "-s", "one more summary",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("STOP", result.stdout)
        self.assertIn("summaries", result.stdout)
        self.assertIn("--scope summaries", result.stdout)
        self.assertIn("never automatic", result.stdout.lower())

    def test_compact_scope_all_runs_tasks_archive_and_summaries(self):
        tasks = self.project / ".moss-mem/tasks"
        archive = tasks / "archive" / "2026"
        summaries = self.project / ".moss-mem/summaries"
        archive.mkdir(parents=True)
        summaries.mkdir(parents=True)

        # Active tasks: keep-recent=1 archives the older one
        old_task = tasks / "20260101-100000_task.md"
        new_task = tasks / "20260720-100000_task.md"
        old_task.write_text(
            "# Task old\n\n## Description\nold task\n\n## Key Decisions\ntoken refresh race\n",
            encoding="utf-8",
        )
        new_task.write_text(
            "# Task new\n\n## Description\nnew task\n\n## Key Decisions\nkeep active\n",
            encoding="utf-8",
        )
        os.utime(old_task, (1_700_000_000, 1_700_000_000))
        os.utime(new_task, (1_800_000_000, 1_800_000_000))

        # Archive: older full body gets re-summarized; newest kept
        arch_old = archive / "20260102-arch_task.md"
        arch_new = archive / "20260721-arch_task.md"
        arch_old.write_text(
            "# Full Archive\n\n## Description\narch\n\n## Key Decisions\ntoken refresh race\n\n"
            "## Scratch\n" + ("noise " * 400) + "\n",
            encoding="utf-8",
        )
        arch_new.write_text(
            "# Compacted from recent\n\n## Key Decisions\narchive recent\n",
            encoding="utf-8",
        )
        os.utime(arch_old, (1_700_000_100, 1_700_000_100))
        os.utime(arch_new, (1_800_000_100, 1_800_000_100))

        # Summaries: merge older into digest; keep newest
        for idx, day in enumerate(("03", "04")):
            p = summaries / f"202601{day}-10000{idx}-topic.md"
            p.write_text(
                "---\ntopic: t%s\n---\n\n# S\n\n## Summary\ns\n\n## Decisions\nhttpOnly cookie\n"
                % day,
                encoding="utf-8",
            )
            os.utime(p, (1_700_000_200, 1_700_000_200))
        recent_sum = summaries / "20260722-999999-recent.md"
        recent_sum.write_text(
            "---\ntopic: recent\n---\n\n# S\n\n## Summary\nkeep\n\n## Decisions\nrecent only\n",
            encoding="utf-8",
        )
        os.utime(recent_sum, (1_800_000_200, 1_800_000_200))

        result = self.run_cli(
            "state", "compact", "--scope", "all",
            "--keep-recent", "1", "--yes",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("scope=all", result.stdout)
        self.assertIn("[tasks]", result.stdout)
        self.assertIn("[archive]", result.stdout)
        self.assertIn("[summaries]", result.stdout)

        # tasks: only newest remains active; old moved into archive/
        self.assertFalse(old_task.exists())
        self.assertTrue(new_task.exists())
        archived_old = list((tasks / "archive").rglob("*20260101-100000_task.md"))
        self.assertTrue(archived_old, result.stdout)
        self.assertIn("token refresh race", archived_old[0].read_text(encoding="utf-8"))

        # archive: old body re-summarized
        arch_body = arch_old.read_text(encoding="utf-8")
        self.assertIn("token refresh race", arch_body)
        self.assertIn("# Compacted from", arch_body)
        self.assertNotIn("noise noise", arch_body)

        # summaries: digest created; recent kept
        digest = summaries / "digest-2026-01.md"
        self.assertTrue(digest.exists(), result.stdout)
        self.assertIn("httpOnly cookie", digest.read_text(encoding="utf-8"))
        self.assertTrue(recent_sum.exists())
        self.assertEqual(len(list(summaries.glob("202601*.md"))), 0)

        (self.project / "MEMORY.md").write_text("# MEMORY\n", encoding="utf-8")
        self.assertEqual(self.run_cli("knowledge-index").returncode, 0)
        for term in ("token refresh race", "httpOnly cookie"):
            search = self.run_cli("memory-search", term)
            self.assertEqual(search.returncode, 0, search.stderr + search.stdout)
            self.assertIn(term, search.stdout)

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
