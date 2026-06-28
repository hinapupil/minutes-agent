from __future__ import annotations

from agent.agent import root_agent

try:
    from google.adk.apps import App
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("google-adk is required to run the ADK app") from exc

app = App(name="minutes-agent", root_agent=root_agent)

