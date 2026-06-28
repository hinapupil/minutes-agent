from __future__ import annotations

import unittest

from minutes_agent.json_utils import ensure_list, extract_json_payload


class JsonUtilsTest(unittest.TestCase):
    def test_extracts_fenced_json_array(self) -> None:
        payload = extract_json_payload(
            """```json
            [{"title": "確認する"}]
            ```"""
        )
        self.assertEqual(payload, [{"title": "確認する"}])

    def test_extracts_first_json_object_from_text(self) -> None:
        payload = extract_json_payload('前置き {"items": [{"id": 1}]} 後置き')
        self.assertEqual(payload, {"items": [{"id": 1}]})

    def test_ensure_list_reads_action_items_key(self) -> None:
        self.assertEqual(ensure_list({"action_items": [{"title": "A"}]}), [{"title": "A"}])


if __name__ == "__main__":
    unittest.main()

