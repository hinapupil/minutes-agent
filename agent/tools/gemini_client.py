from __future__ import annotations

from minutes_agent.config import Settings


class GeminiTextClient:
    def __init__(self, settings: Settings) -> None:
        from google import genai

        self._settings = settings
        if settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        else:
            settings.require("google_cloud_project")
            self._client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )

    def generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._settings.gemini_model,
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if text:
            return str(text).strip()
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            raise RuntimeError("Gemini response did not contain candidates")
        parts = getattr(candidates[0].content, "parts", []) or []
        collected = [getattr(part, "text", "") for part in parts if getattr(part, "text", "")]
        if not collected:
            raise RuntimeError("Gemini response did not contain text")
        return "\n".join(collected).strip()
