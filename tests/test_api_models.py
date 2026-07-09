from __future__ import annotations

import unittest

from api.tasks import ActionsCommandRequest
from minutes_agent.discord_commands import interaction_command_payloads


class ApiModelsTest(unittest.TestCase):
    def test_actions_request_accepts_status_filter(self) -> None:
        payload = ActionsCommandRequest.model_validate({"status": "completed", "limit": 10})

        self.assertEqual(payload.status, "completed")
        self.assertEqual(payload.limit, 10)

    def test_actions_request_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValueError):
            ActionsCommandRequest.model_validate({"status": "blocked"})

    def test_interaction_command_payloads_do_not_include_gateway_commands(self) -> None:
        names = {command["name"] for command in interaction_command_payloads()}

        self.assertEqual(names, {"minutes", "ask", "actions", "action-done"})


if __name__ == "__main__":
    unittest.main()
