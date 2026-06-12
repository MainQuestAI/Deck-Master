from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from runtime.events import (  # noqa: E402
    CANONICAL_SCHEMA_VERSION,
    EVENT_TYPES,
    append_event,
    append_typed_event,
    events_path,
    read_events,
)


class LegacyAppendEventTests(unittest.TestCase):
    """旧 append_event API 向后兼容测试。"""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_append_event_writes_legacy_fields(self) -> None:
        event = append_event(self.temp_dir, "run.created", status="ok", actor="deck_master")
        self.assertEqual("run.created", event["action"])
        self.assertEqual("ok", event["status"])
        self.assertEqual("deck_master", event["actor"])
        self.assertIn("timestamp", event)
        # legacy 事件不应包含 canonical 字段
        self.assertNotIn("schema_version", event)
        self.assertNotIn("event_type", event)

    def test_append_event_requires_action(self) -> None:
        with self.assertRaises(ValueError):
            append_event(self.temp_dir, "")

    def test_read_events_returns_legacy_events(self) -> None:
        append_event(self.temp_dir, "first.event")
        append_event(self.temp_dir, "second.event")
        events = read_events(self.temp_dir)
        self.assertEqual(2, len(events))
        self.assertEqual(["first.event", "second.event"], [e["action"] for e in events])


class TypedEventTests(unittest.TestCase):
    """新 append_typed_event canonical schema 测试。"""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_typed_event_contains_all_canonical_fields(self) -> None:
        event = append_typed_event(
            self.temp_dir,
            "step_started",
            step="intake",
            message="开始需求澄清",
            run_id="run-001",
            refs=["brief.md"],
            severity="info",
        )
        self.assertEqual(CANONICAL_SCHEMA_VERSION, event["schema_version"])
        self.assertEqual("step_started", event["event_type"])
        self.assertEqual("intake", event["step"])
        self.assertEqual("开始需求澄清", event["message"])
        self.assertEqual("run-001", event["run_id"])
        self.assertEqual(["brief.md"], event["refs"])
        self.assertEqual("info", event["severity"])
        self.assertIn("timestamp", event)
        # action 默认等于 step
        self.assertEqual("intake", event["action"])
        # status 由 event_type 推断
        self.assertEqual("started", event["status"])

    def test_typed_event_status_inference(self) -> None:
        cases = {
            "step_started": "started",
            "step_completed": "completed",
            "error": "error",
            "tool_call": "ok",
            "decision": "ok",
            "manual_action": "ok",
            "artifact_written": "ok",
        }
        for event_type, expected_status in cases.items():
            with self.subTest(event_type=event_type):
                temp = Path(tempfile.mkdtemp())
                try:
                    event = append_typed_event(temp, event_type, step="s", message="m")
                    self.assertEqual(expected_status, event["status"])
                finally:
                    shutil.rmtree(temp, ignore_errors=True)

    def test_typed_event_explicit_status_overrides_inference(self) -> None:
        event = append_typed_event(
            self.temp_dir, "step_started", step="s", message="m", status="custom"
        )
        self.assertEqual("custom", event["status"])

    def test_typed_event_explicit_action_overrides_step(self) -> None:
        event = append_typed_event(
            self.temp_dir, "tool_call", step="generate", message="m", action="custom.action"
        )
        self.assertEqual("custom.action", event["action"])

    def test_typed_event_payload_included_when_provided(self) -> None:
        payload = {"model": "gpt-4o", "tokens": 1234}
        event = append_typed_event(
            self.temp_dir, "tool_call", step="gen", message="m", payload=payload
        )
        self.assertEqual(payload, event["payload"])

    def test_typed_event_no_payload_key_when_none(self) -> None:
        event = append_typed_event(self.temp_dir, "decision", step="d", message="m")
        self.assertNotIn("payload", event)

    def test_invalid_event_type_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            append_typed_event(self.temp_dir, "invalid_type", step="s", message="m")
        self.assertIn("invalid_type", str(ctx.exception))
        # 错误消息应列出所有合法类型
        for valid in sorted(EVENT_TYPES):
            self.assertIn(valid, str(ctx.exception))

    def test_typed_event_persisted_to_disk(self) -> None:
        append_typed_event(self.temp_dir, "artifact_written", step="write", message="done")
        events = read_events(self.temp_dir)
        self.assertEqual(1, len(events))
        self.assertEqual("artifact_written", events[0]["event_type"])
        self.assertEqual(CANONICAL_SCHEMA_VERSION, events[0]["schema_version"])


class ReadEventsRobustnessTests(unittest.TestCase):
    """read_events 严格/非严格模式与混合格式测试。"""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_empty_file_returns_empty_list(self) -> None:
        path = events_path(self.temp_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        self.assertEqual([], read_events(self.temp_dir))

    def test_missing_file_returns_empty_list(self) -> None:
        self.assertEqual([], read_events(self.temp_dir))

    def test_non_strict_skips_bad_json_lines(self) -> None:
        path = events_path(self.temp_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"action":"good.one"}\n'
            "NOT-JSON\n"
            '{"action":"good.two"}\n',
            encoding="utf-8",
        )
        events = read_events(self.temp_dir)
        self.assertEqual(2, len(events))
        self.assertEqual(["good.one", "good.two"], [e["action"] for e in events])

    def test_non_strict_skips_non_object_lines(self) -> None:
        path = events_path(self.temp_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"action":"obj"}\n'
            '"just a string"\n'
            "[1, 2, 3]\n",
            encoding="utf-8",
        )
        events = read_events(self.temp_dir)
        self.assertEqual(1, len(events))
        self.assertEqual("obj", events[0]["action"])

    def test_strict_raises_on_bad_json(self) -> None:
        path = events_path(self.temp_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"action":"ok"}\nBAD\n', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            read_events(self.temp_dir, strict=True)
        self.assertIn("line 2", str(ctx.exception))

    def test_strict_raises_on_non_object(self) -> None:
        path = events_path(self.temp_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('"not an object"\n', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            read_events(self.temp_dir, strict=True)
        self.assertIn("line 1", str(ctx.exception))

    def test_legacy_and_typed_events_coexist(self) -> None:
        append_event(self.temp_dir, "legacy.action", status="ok")
        append_typed_event(
            self.temp_dir, "step_completed", step="build", message="完成构建", run_id="r1"
        )
        append_event(self.temp_dir, "another.legacy")
        events = read_events(self.temp_dir)
        self.assertEqual(3, len(events))
        # 第一条是旧格式
        self.assertNotIn("schema_version", events[0])
        self.assertEqual("legacy.action", events[0]["action"])
        # 第二条是新格式
        self.assertEqual(CANONICAL_SCHEMA_VERSION, events[1]["schema_version"])
        self.assertEqual("step_completed", events[1]["event_type"])
        # 第三条又是旧格式
        self.assertNotIn("schema_version", events[2])
        self.assertEqual("another.legacy", events[2]["action"])

    def test_blank_lines_are_ignored(self) -> None:
        path = events_path(self.temp_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n\n{\"action\":\"a\"}\n\n{\"action\":\"b\"}\n\n", encoding="utf-8"
        )
        events = read_events(self.temp_dir)
        self.assertEqual(2, len(events))


if __name__ == "__main__":
    unittest.main()
