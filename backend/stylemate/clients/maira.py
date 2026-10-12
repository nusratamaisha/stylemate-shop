"""Talks to Maira: asking questions, generating pictures, and uploading and training the dataset."""

import base64
import re
import time
from dataclasses import dataclass
from typing import Callable

from ..errors import ServiceUnavailableError
from .base import GigalogyClient

IMAGE_TIMEOUT_SECONDS = 120.0  # a picture takes far longer than a text answer
IMAGE_URL = re.compile(r"https?://[^\s\"'<>)\]]+\.(?:png|jpe?g|webp)(?:\?[^\s\"'<>)\]]*)?", re.IGNORECASE)


@dataclass(frozen=True)
class Reference:
    """One piece of shop data Maira found while answering (one product row)."""

    section_id: str  # our product code, e.g. "SR-002"
    dataset_id: str
    score: float


@dataclass(frozen=True)
class MairaAnswer:
    text: str
    session_id: str
    conversation_id: str
    references: list[Reference]
    prompt_tokens: int
    completion_tokens: int

    @property
    def top_score(self) -> float | None:
        return max((ref.score for ref in self.references), default=None)


@dataclass(frozen=True)
class ReferenceImage:
    """A picture sent along with an image prompt: the dress photo, or the customer's own photo."""

    filename: str
    content: bytes
    mimetype: str

    @property
    def data_url(self) -> str:
        return f"data:{self.mimetype};base64,{base64.b64encode(self.content).decode('ascii')}"


@dataclass(frozen=True)
class GeneratedImage:
    url: str
    conversation_id: str


class MairaClient(GigalogyClient):
    service_name = "Maira"

    def __init__(self, *args, read_checks: int = 10, read_interval: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep, **kwargs):
        super().__init__(*args, **kwargs)
        self._read_checks = read_checks  # how many times to check that an uploaded file has been read
        self._read_interval = read_interval
        self._sleep = sleep  # passed in so tests don't really wait

    def ask(self, *, user_id: str, query: str, profile_id: str,
            session_id: str | None = None) -> MairaAnswer:
        body = {
            "user_id": user_id,
            "query": query,
            "conversation_type": "chat",
            "gpt_profile_id": profile_id,
        }
        if session_id:
            body["session_id"] = session_id
        data = self._request("POST", "/v1/maira/ask", json=body)
        return parse_answer(data)

    def generate_image(self, *, user_id: str, prompt: str, profile_id: str,
                       reference_images: list[ReferenceImage] | None = None) -> GeneratedImage:
        """Ask an image profile for a picture.

        It is the same endpoint as ask(): Maira draws instead of writing when the
        profile's model is an image model. Reference images guide the picture.
        """
        body = {
            "user_id": user_id,
            "query": prompt,
            "conversation_type": "chat",
            "gpt_profile_id": profile_id,
        }
        if reference_images:
            body["images"] = [{"filename": image.filename, "file_content": image.data_url}
                              for image in reference_images]
        data = self._request("POST", "/v1/maira/ask", json=body, timeout=IMAGE_TIMEOUT_SECONDS)
        return parse_generated_image(data)

    def get_dataset(self, dataset_id: str) -> dict:
        """A dataset's settings, including its "tags"."""
        data = self._request("GET", f"/v1/gpt/datasets/{dataset_id}")
        # Unlike ask, this one answers {"response": {"dataset": {...}}} with no "detail" wrapper
        response = data.get("detail", data).get("response") or {}
        return response.get("dataset") or {}

    def create_dataset(self, *, name: str, idx_column: str, tags: list[str], description: str = "") -> str:
        """Create an empty dataset and return its ID."""
        body = {"name": name, "idx_column_name": idx_column, "tags": tags, "description": description}
        data = self._request("POST", "/v1/gpt/datasets", json=body)
        dataset_id = _find_key(data, "dataset_id")
        if not dataset_id:
            raise ServiceUnavailableError("Maira created a dataset but didn't return its ID")
        return dataset_id

    def upload_dataset_file(self, dataset_id: str, filename: str, content: bytes) -> dict:
        """Add or replace documents from a CSV (rows with an existing ID replace that document)."""
        files = {"dataset_file": (filename, content, "text/csv")}
        return self._request("PUT", f"/v1/gpt/datasets/{dataset_id}/file", files=files)

    def upload_and_train(self, dataset_id: str, filename: str, content: bytes) -> None:
        """Upload a CSV, wait until Maira has read it, then start training.

        Maira reads the file in the background (about 2 seconds, measured Oct 11). A train
        call sent before that finishes trains nothing, and the assistant never learns the
        changes. Once the file is read, the new documents show as untrained; that is the signal.
        """
        self.upload_dataset_file(dataset_id, filename, content)
        for _ in range(self._read_checks):
            self._sleep(self._read_interval)
            counts = self.get_dataset(dataset_id).get("documents_count") or {}
            if counts.get("text_trained", 0) < counts.get("total", 0):
                break
        # If the signal never came, train anyway: training an unchanged dataset does no harm.
        self.train_dataset(dataset_id)

    def train_dataset(self, dataset_id: str) -> dict:
        body = {"train_type": "text", "batch_size": 1, "only_payload_update": False}
        return self._request("POST", f"/v1/gpt/datasets/{dataset_id}/train", json=body)


def parse_answer(data: dict) -> MairaAnswer:
    """Turn Maira's response into a MairaAnswer. The real answer is wrapped in "detail"."""
    detail = data.get("detail", data)
    usage = detail.get("usage") or {}
    references = [
        Reference(
            section_id=str(ref.get("section_id", "")),
            dataset_id=str(ref.get("dataset_id", "")),
            score=_to_float(ref.get("similarity_score")),  # Maira sends scores as strings
        )
        for ref in detail.get("references") or []
    ]
    return MairaAnswer(
        text=(detail.get("response") or "").strip(),
        session_id=detail.get("session_id") or "",
        conversation_id=detail.get("conversation_id") or "",
        references=references,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
    )


def parse_generated_image(data: dict) -> GeneratedImage:
    """Find the picture's URL in Maira's response.

    Pictures arrive in "generated_images" (seen Oct 11, but only empty, so the shape
    of one entry is still unknown and the link is searched for). When the image model
    fails, Maira still answers 200 and puts the reason in "response" as text.
    """
    detail = data.get("detail", data)
    url = find_image_url(detail.get("generated_images")) or find_image_url(detail.get("response"))
    if not url:
        reason = str(detail.get("response") or "no reason given")[:300]
        raise ServiceUnavailableError(f"Maira answered without a picture: {reason}")
    return GeneratedImage(url=url, conversation_id=detail.get("conversation_id") or "")


def find_image_url(value) -> str:
    if isinstance(value, str):
        match = IMAGE_URL.search(value)
        return match.group(0) if match else ""
    children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
    for child in children:
        url = find_image_url(child)
        if url:
            return url
    return ""


def _find_key(value, key: str) -> str:
    """The first value stored under `key` anywhere in a response, or ""."""
    if isinstance(value, dict):
        if isinstance(value.get(key), str):
            return value[key]
        value = list(value.values())
    if isinstance(value, list):
        for child in value:
            found = _find_key(child, key)
            if found:
                return found
    return ""


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
