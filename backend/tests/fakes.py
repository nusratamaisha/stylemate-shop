"""Stand-ins for the Maira, Chorus and recommender clients, so tests never call the real APIs.

They have the same methods as the real clients, so the app can't tell the difference.
"""

from stylemate.clients.maira import GeneratedImage, MairaAnswer, Reference, ReferenceImage
from stylemate.errors import ServiceUnavailableError


class FakeMaira:
    def __init__(self, answer: str = "Try the **Shefali Embroidered Maxi**.", top_score: float = 42.5):
        self.answer = answer
        self.top_score = top_score
        self.fail = False
        self.asked: list[dict] = []
        self.uploads: list[tuple] = []
        self.trained: list[str] = []
        self.image_requests: list[dict] = []
        self.downloaded: list[str] = []
        self.created_datasets: list[dict] = []

    def ask(self, *, user_id, query, profile_id, session_id=None):
        if self.fail:
            raise ServiceUnavailableError("Maira is down")
        self.asked.append({"user_id": user_id, "query": query, "profile_id": profile_id,
                           "session_id": session_id})
        references = [Reference("SR-002", "dataset-1", self.top_score)] if self.top_score else []
        return MairaAnswer(text=self.answer, session_id=session_id or "session-1",
                           conversation_id="conversation-1", references=references,
                           prompt_tokens=1600, completion_tokens=40)

    def generate_image(self, *, user_id, prompt, profile_id, reference_images=None):
        if self.fail:
            raise ServiceUnavailableError("Maira is down")
        self.image_requests.append({"user_id": user_id, "prompt": prompt, "profile_id": profile_id,
                                    "reference_images": list(reference_images or [])})
        return GeneratedImage(url="https://images.test/preview-1.png", conversation_id="conversation-2")

    def download_image(self, url):
        if self.fail:
            raise ServiceUnavailableError("Maira is down")
        self.downloaded.append(url)
        return ReferenceImage("preview-1.png", b"\x89PNG drawn picture", "image/png")

    def get_dataset(self, dataset_id):
        return {"dataset_id": dataset_id, "tags": ["house_of_m"]}

    def create_dataset(self, *, name, idx_column, tags, description=""):
        self.created_datasets.append({"name": name, "idx_column": idx_column, "tags": tags})
        return f"help-dataset-{len(self.created_datasets)}"

    def upload_dataset_file(self, dataset_id, filename, content):
        if self.fail:
            raise ServiceUnavailableError("Maira is down")
        self.uploads.append((dataset_id, filename, content))
        return {}

    def upload_and_train(self, dataset_id, filename, content):
        self.upload_dataset_file(dataset_id, filename, content)
        self.train_dataset(dataset_id)

    def train_dataset(self, dataset_id):
        self.trained.append(dataset_id)
        return {}


class FakeRecommender:
    """Gigalogy's recommender, without the network. `similar` is the IDs it answers with."""

    def __init__(self):
        self.similar: list[str] = []
        self.fail = False
        self.calls: list[tuple] = []
        self.indices = ["gpt_dataset", "gpt_profiles", "chorus"]  # a Maira project: no item index yet
        self.uploads: list[tuple] = []

    def _check(self):
        if self.fail:
            raise ServiceUnavailableError("Recommender is down")

    def get_indices(self):
        self._check()
        return {"detail": {"response": list(self.indices)}}

    def has_item_index(self):
        return "items" in self.get_indices()["detail"]["response"]

    def create_indices(self):
        self.calls.append(("create_indices",))
        self.indices.append("items")
        return {"detail": "ok"}

    def save_mapper(self, key_map):
        self.calls.append(("save_mapper", key_map))
        return {"detail": "ok"}

    def upload_items(self, filename, content):
        self._check()
        self.uploads.append((filename, content))
        return {"detail": "ok"}

    def train_items(self):
        self.calls.append(("train_items",))
        return {"detail": "ok"}

    def similar_items(self, *, user_id, item_id, member_id=None):
        self._check()
        self.calls.append(("similar_items", user_id, item_id, member_id))
        return list(self.similar)


class FakeChorus:
    def __init__(self, transcript: str = "Do you have a dress for a wedding?"):
        self.transcript = transcript
        self.received: list[bytes] = []

    def transcribe(self, audio, filename="question.wav", mimetype="audio/wav", language="auto"):
        self.received.append(audio)
        return self.transcript
