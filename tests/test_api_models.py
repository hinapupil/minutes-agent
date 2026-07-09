from __future__ import annotations

import unittest

from api.tasks import ActionsCommandRequest


class ApiModelsTest(unittest.TestCase):
    def test_actions_request_accepts_status_filter(self) -> None:
        payload = ActionsCommandRequest.model_validate({"status": "completed", "limit": 10})

        self.assertEqual(payload.status, "completed")
        self.assertEqual(payload.limit, 10)

    def test_actions_request_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValueError):
            ActionsCommandRequest.model_validate({"status": "blocked"})


if __name__ == "__main__":
    unittest.main()

