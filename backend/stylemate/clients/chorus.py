"""Talks to Maira Chorus (speech-to-text).

Chorus is asynchronous: upload the audio, get a task ID, then check the task
until it is completed or failed.
"""

import time
from typing import Callable

from ..errors import ServiceUnavailableError
from .base import GigalogyClient


class ChorusClient(GigalogyClient):
    service_name = "Chorus"

    def __init__(self, *args, poll_interval: float = 1.0, max_wait: float = 20.0,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic, **kwargs):
        super().__init__(*args, **kwargs)
        self._poll_interval = poll_interval
        self._max_wait = max_wait
        self._sleep = sleep  # passed in so tests don't really wait
        self._clock = clock

    def transcribe(self, audio: bytes, filename: str = "question.wav",
                   mimetype: str = "audio/wav", language: str = "auto") -> str:
        """Return the spoken text, or "" if no speech was heard."""
        task = self._request(
            "POST", "/v1/speeches",
            files={"file": (filename, audio, mimetype)},
            data={"task_type": "transcription", "language": language},
        )
        task_id = task["task_id"]
        deadline = self._clock() + self._max_wait

        while True:
            result = self._request("GET", f"/v1/speeches/{task_id}")
            status = result.get("status")
            if status == "completed":
                transcription = (result.get("results") or {}).get("transcription") or {}
                return (transcription.get("text") or "").strip()
            if status == "failed":
                raise ServiceUnavailableError("Chorus could not transcribe the recording")
            if self._clock() >= deadline:
                raise ServiceUnavailableError("Chorus took too long to transcribe the recording")
            self._sleep(self._poll_interval)
