from __future__ import annotations

import unittest

from scripts.runtime.schema import (
    SchemaVersionError,
    check_schema_version,
    ensure_schema_version,
    read_with_schema,
    schema_version,
    write_with_schema,
)


class TestSchemaVersion(unittest.TestCase):
    def test_returns_tag(self) -> None:
        self.assertEqual(schema_version("deck_workspace.v1"), "deck_workspace.v1")


class TestEnsureSchemaVersion(unittest.TestCase):
    def test_adds_missing_tag(self) -> None:
        data: dict = {"foo": "bar"}
        result = ensure_schema_version(data, "deck_workspace.v1")
        self.assertEqual(result["schema_version"], "deck_workspace.v1")
        # 应返回同一个 dict
        self.assertIs(result, data)

    def test_preserves_existing_tag(self) -> None:
        data = {"schema_version": "custom.v2", "foo": "bar"}
        result = ensure_schema_version(data, "deck_workspace.v1")
        self.assertEqual(result["schema_version"], "custom.v2")


class TestCheckSchemaVersion(unittest.TestCase):
    def test_matching_returns_true(self) -> None:
        data = {"schema_version": "deck_workspace.v1"}
        self.assertTrue(check_schema_version(data, "deck_workspace.v1"))

    def test_missing_returns_true_legacy(self) -> None:
        data: dict = {"foo": "bar"}
        self.assertTrue(check_schema_version(data, "deck_workspace.v1"))

    def test_mismatching_returns_false(self) -> None:
        data = {"schema_version": "deck_workspace.v2"}
        self.assertFalse(check_schema_version(data, "deck_workspace.v1"))


class TestReadWithSchema(unittest.TestCase):
    def test_missing_tag_adds_and_returns(self) -> None:
        data: dict = {"foo": "bar"}
        result = read_with_schema(data, "deck_workspace.v1")
        self.assertEqual(result["schema_version"], "deck_workspace.v1")
        self.assertIs(result, data)

    def test_matching_tag_returns_directly(self) -> None:
        data = {"schema_version": "deck_workspace.v1", "foo": "bar"}
        result = read_with_schema(data, "deck_workspace.v1")
        self.assertIs(result, data)

    def test_mismatching_tag_raises(self) -> None:
        data = {"schema_version": "deck_workspace.v2"}
        with self.assertRaises(SchemaVersionError):
            read_with_schema(data, "deck_workspace.v1")


class TestWriteWithSchema(unittest.TestCase):
    def test_sets_tag(self) -> None:
        data: dict = {"foo": "bar"}
        result = write_with_schema(data, "deck_event.v1")
        self.assertEqual(result["schema_version"], "deck_event.v1")
        self.assertIs(result, data)


if __name__ == "__main__":
    unittest.main()
