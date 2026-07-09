from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from minutes_agent.config import Settings
from minutes_agent.models import TranscriptSegment


class SpeechTranscriber:
    def __init__(self, settings: Settings) -> None:
        settings.require("google_cloud_project")
        from google.cloud import speech_v2

        self._settings = settings
        self._client = speech_v2.SpeechClient()

    def transcribe_uri(
        self,
        gcs_uri: str,
        *,
        speaker_id: str,
        speaker_name: str | None = None,
    ) -> list[TranscriptSegment]:
        from google.cloud.speech_v2.types import cloud_speech

        config = self._recognition_config()
        request = cloud_speech.BatchRecognizeRequest(
            recognizer=self._settings.recognizer_path,
            config=config,
            files=[cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)],
            recognition_output_config=cloud_speech.RecognitionOutputConfig(
                inline_response_config=cloud_speech.InlineOutputConfig()
            ),
        )
        operation = self._client.batch_recognize(request=request)
        response = operation.result(timeout=self._settings.speech_batch_timeout_seconds)
        file_result = response.results.get(gcs_uri)
        if file_result is None and response.results:
            file_result = next(iter(response.results.values()))
        if file_result is None:
            raise RuntimeError(f"Speech-to-Text returned no result for {gcs_uri}")
        if file_result.error and file_result.error.code:
            raise RuntimeError(file_result.error.message)
        return self._segments_from_results(
            file_result.inline_result.transcript.results,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
        )

    def _recognition_config(self) -> Any:
        from google.cloud.speech_v2.types import cloud_speech

        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=list(self._settings.speech_language_codes),
            model=self._settings.speech_model,
            features=cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                diarization_config=(
                    cloud_speech.SpeakerDiarizationConfig(
                        min_speaker_count=self._settings.speech_min_speaker_count,
                        max_speaker_count=self._settings.speech_max_speaker_count,
                    )
                    if self._settings.speech_enable_diarization
                    else None
                ),
            ),
        )
        return config

    def _segments_from_results(
        self,
        results: Iterable[Any],
        *,
        speaker_id: str,
        speaker_name: str | None,
    ) -> list[TranscriptSegment]:
        segments: list[TranscriptSegment] = []
        cursor = 0.0
        for result in results:
            if not result.alternatives:
                continue
            alternative = result.alternatives[0]
            diarized = _segments_from_diarized_words(
                alternative.words,
                speaker_id=speaker_id,
                speaker_name=speaker_name,
            )
            if diarized:
                segments.extend(diarized)
                cursor = diarized[-1].end_seconds or cursor
                continue
            text = alternative.transcript.strip()
            if not text:
                continue
            end_seconds = _duration_to_seconds(getattr(result, "result_end_offset", None))
            segments.append(
                TranscriptSegment(
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    text=text,
                    start_seconds=cursor,
                    end_seconds=end_seconds,
                )
            )
            if end_seconds is not None:
                cursor = end_seconds
        return segments


def _segments_from_diarized_words(
    words: Iterable[Any],
    *,
    speaker_id: str,
    speaker_name: str | None,
) -> list[TranscriptSegment]:
    grouped: list[TranscriptSegment] = []
    current_label: str | None = None
    current_words: list[str] = []
    current_start: float | None = None
    current_end: float | None = None

    for word in words:
        label = str(getattr(word, "speaker_label", "") or "").strip()
        if not label:
            return []
        word_text = str(getattr(word, "word", "") or "").strip()
        if not word_text:
            continue
        if current_label is not None and label != current_label and current_words:
            grouped.append(
                _build_diarized_segment(
                    speaker_id,
                    speaker_name,
                    current_label,
                    current_words,
                    current_start,
                    current_end,
                )
            )
            current_words = []
            current_start = None
            current_end = None
        current_label = label
        current_words.append(word_text)
        current_start = current_start or _duration_to_seconds(getattr(word, "start_offset", None))
        current_end = _duration_to_seconds(getattr(word, "end_offset", None)) or current_end

    if current_label is not None and current_words:
        grouped.append(
            _build_diarized_segment(
                speaker_id,
                speaker_name,
                current_label,
                current_words,
                current_start,
                current_end,
            )
        )
    return grouped


def _build_diarized_segment(
    speaker_id: str,
    speaker_name: str | None,
    label: str,
    words: list[str],
    start_seconds: float | None,
    end_seconds: float | None,
) -> TranscriptSegment:
    base_name = speaker_name or speaker_id
    return TranscriptSegment(
        speaker_id=f"{speaker_id}:{label}",
        speaker_name=f"{base_name}:{label}",
        text=_join_words(words),
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )


def _join_words(words: list[str]) -> str:
    if all(word.isascii() for word in words):
        return " ".join(words)
    return "".join(words)


def _duration_to_seconds(value: object) -> float | None:
    if value is None:
        return None
    seconds = getattr(value, "seconds", 0) or 0
    nanos = getattr(value, "nanos", 0) or 0
    return float(seconds) + float(nanos) / 1_000_000_000
