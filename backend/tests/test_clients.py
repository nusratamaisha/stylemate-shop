"""The Maira and Chorus clients, tested with a fake HTTP session (no network)."""
#(10 tests)
import pytest
import requests
import json

from stylemate.clients import ChorusClient, MairaClient, ReferenceImage
from stylemate.errors import ServiceUnavailableError


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data
        self.text = str(data)

    def json(self):
        return self._data


class FakeHttp:
    """Records each request and replays the queued responses in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


# Shortened copy of a real response from Oct 6
MAIRA_RESPONSE = {
    "detail": {
        "session_id": "2f558e57",
        "response": "The **Shefali Embroidered Maxi** is made for wedding receptions.",
        "references": [
            {"section_id": "SR-002", "similarity_score": "42.53", "dataset_id": "c1fef7d8"},
            {"section_id": "SR-005", "similarity_score": "36.17", "dataset_id": "c1fef7d8"},
        ],
        "usage": {"prompt_tokens": 1662, "completion_tokens": 120},
        "conversation_id": "fc825544",
    }
}


def test_ask_sends_keys_and_parses_the_detail_wrapper():
    http = FakeHttp(FakeResponse(200, MAIRA_RESPONSE))
    client = MairaClient("https://maira.test/", "project-key-1", "api-key-1", http=http)

    answer = client.ask(user_id="visitor-1", query="Wedding dress?", profile_id="profile-1")

    sent = http.requests[0]
    payload = json.loads(sent["files"]["payload"][1])  # iask: the JSON is a text part of a multipart form
    assert sent["url"] == "https://maira.test/v1/maira/iask"
    assert sent["headers"] == {"project-key": "project-key-1", "api-key": "api-key-1"}
    assert payload["gpt_profile_id"] == "profile-1"
    assert payload["conversation_type"] == "chat"  # iask's default "question" would forget follow-ups
    assert "session_id" not in payload
    assert answer.text.startswith("The **Shefali")
    assert answer.session_id == "2f558e57"
    assert answer.top_score == 42.53  # converted from the string "42.53"
    assert answer.prompt_tokens == 1662


def test_ask_sends_session_id_for_follow_ups():
    http = FakeHttp(FakeResponse(200, MAIRA_RESPONSE))
    MairaClient("https://maira.test", "p", "a", http=http).ask(
        user_id="v", query="Does it come in XL?", profile_id="p1", session_id="2f558e57")
    assert json.loads(http.requests[0]["files"]["payload"][1])["session_id"] == "2f558e57"



def test_top_score_is_none_without_references():
    http = FakeHttp(FakeResponse(200, {"detail": {"response": "Hi", "references": []}}))
    answer = MairaClient("https://maira.test", "p", "a", http=http).ask(user_id="v", query="hi", profile_id="p1")
    assert answer.top_score is None


@pytest.mark.parametrize("failure", [FakeResponse(401, {"detail": "bad key"}),
                                     requests.ConnectionError("offline")])
def test_maira_failures_become_service_unavailable(failure):
    client = MairaClient("https://maira.test", "p", "a", http=FakeHttp(failure))
    with pytest.raises(ServiceUnavailableError):
        client.ask(user_id="v", query="hi", profile_id="p1")


def chorus_client(http, clock_values=None):
    ticks = iter(clock_values or [0, 0, 0, 0, 0])
    return ChorusClient("https://chorus.test", "p", "a", http=http,
                        sleep=lambda seconds: None, clock=lambda: next(ticks), max_wait=20)


def test_transcribe_uploads_then_polls_until_completed():
    http = FakeHttp(
        FakeResponse(200, {"task_id": "task-1", "status": "queued"}),
        FakeResponse(200, {"status": "processing"}),
        FakeResponse(200, {"status": "completed",
                           "results": {"transcription": {"text": " Dress in red color in size M "}}}),
    )
    text = chorus_client(http).transcribe(b"RIFF...", filename="q.wav")

    assert text == "Dress in red color in size M"
    upload = http.requests[0]
    assert upload["url"] == "https://chorus.test/v1/speeches"
    assert upload["data"] == {"task_type": "transcription", "language": "auto"}
    assert http.requests[2]["url"] == "https://chorus.test/v1/speeches/task-1"


def test_transcribe_returns_empty_text_when_no_speech():
    http = FakeHttp(
        FakeResponse(200, {"task_id": "task-1", "status": "queued"}),
        FakeResponse(200, {"status": "completed", "results": {"transcription": {"text": ""}}}),
    )
    assert chorus_client(http).transcribe(b"...") == ""


def test_transcribe_gives_up_after_max_wait():
    http = FakeHttp(
        FakeResponse(200, {"task_id": "task-1", "status": "queued"}),
        FakeResponse(200, {"status": "processing"}),
    )
    with pytest.raises(ServiceUnavailableError, match="too long"):
        chorus_client(http, clock_values=[0, 25]).transcribe(b"...")


def test_transcribe_reports_failed_tasks():
    http = FakeHttp(
        FakeResponse(200, {"task_id": "task-1", "status": "queued"}),
        FakeResponse(200, {"status": "failed"}),
    )
    with pytest.raises(ServiceUnavailableError, match="could not transcribe"):
        chorus_client(http).transcribe(b"...")


def test_upload_dataset_file_uses_the_dataset_file_field():
    http = FakeHttp(FakeResponse(200, {"detail": {"response": "Success"}}))
    MairaClient("https://maira.test", "p", "a", http=http).upload_dataset_file(
        "dataset-1", "products.csv", b"id,name\n")

    sent = http.requests[0]
    assert sent["url"] == "https://maira.test/v1/gpt/datasets/dataset-1/file"
    assert sent["files"]["dataset_file"][0] == "products.csv"  # Maira rejects any other field name


def test_upload_and_train_waits_until_maira_has_read_the_file():
    def counts(total, trained):
        return FakeResponse(200, {"response": {"dataset": {"documents_count": {"total": total, "text_trained": trained}}}})

    http = FakeHttp(
        FakeResponse(200, {"detail": {"task_id": "upload-1"}}),
        counts(10, 10),  # still the old documents: the file hasn't been read yet
        counts(10, 0),   # read: the new documents are waiting to be trained
        FakeResponse(202, {"detail": {"task_id": "train-1"}}),
    )
    MairaClient("https://maira.test", "p", "a", http=http, sleep=lambda seconds: None).upload_and_train(
        "dataset-1", "products.csv", b"id,name\n")

    calls = [(request["method"], request["url"].rsplit("/", 1)[-1]) for request in http.requests]
    assert calls == [("PUT", "file"), ("GET", "dataset-1"), ("GET", "dataset-1"), ("POST", "train")]
    # The whole address, not just its end: a typo inside it (Oct 27) made every stock sync fail with a 502
    assert http.requests[-1]["url"] == "https://maira.test/v1/gpt/datasets/dataset-1/train"


def test_get_dataset_reads_the_tags():
    # Real shape from Oct 11: no "detail" wrapper, and the settings sit under "dataset"
    http = FakeHttp(FakeResponse(200, {"response": {"dataset": {"name": "house_of_m", "tags": ["house_of_m"]}}}))
    dataset = MairaClient("https://maira.test", "p", "a", http=http).get_dataset("dataset-1")
    assert dataset["tags"] == ["house_of_m"]


def test_generate_image_sends_reference_images_and_finds_the_picture_url():
    http = FakeHttp(FakeResponse(200, {"detail": {
        "response": "Here is your picture.",
        "conversation_id": "c-9",
        "generated_images": [{"url": "https://bucket.test/gen_123_0.png?sig=abc"}],
    }}))
    client = MairaClient("https://maira.test", "p", "a", http=http)

    image = client.generate_image(user_id="v1", prompt="A red maxi dress", profile_id="image-profile-1",
                                  reference_images=[ReferenceImage("me.png", b"abc", "image/png")])

    sent = http.requests[0]
    assert sent["url"] == "https://maira.test/v1/maira/ask"  # same endpoint as a text question
    assert sent["json"]["query"] == "A red maxi dress"
    assert sent["json"]["gpt_profile_id"] == "image-profile-1"
    assert sent["json"]["images"] == [{"filename": "me.png", "file_content": "data:image/png;base64,YWJj"}]
    assert sent["timeout"] == 120.0  # pictures get longer than the usual 30 seconds
    assert image.url == "https://bucket.test/gen_123_0.png?sig=abc"
    assert image.conversation_id == "c-9"


def test_generate_image_finds_a_url_inside_the_answer_text():
    http = FakeHttp(FakeResponse(200, {"detail": {"response": "![preview](https://bucket.test/a.jpg)"}}))
    image = MairaClient("https://maira.test", "p", "a", http=http).generate_image(
        user_id="v1", prompt="A dress", profile_id="image-profile-1")
    assert image.url == "https://bucket.test/a.jpg"


def test_generate_image_without_a_picture_reports_mairas_reason():
    # Real response from Oct 11: status 200, but the profile's model wasn't available
    http = FakeHttp(FakeResponse(200, {"detail": {
        "response": "Error: Error code: 404 - The model `gpt-image-2.5-sunburst` does not exist",
        "generated_images": [],
    }}))
    with pytest.raises(ServiceUnavailableError, match="without a picture: Error: Error code: 404"):
        MairaClient("https://maira.test", "p", "a", http=http).generate_image(
            user_id="v1", prompt="A dress", profile_id="image-profile-1")


def test_create_dataset_sends_the_tags_and_returns_the_new_id():
    http = FakeHttp(FakeResponse(200, {"detail": {"response": {"dataset_id": "d-77", "name": "shop-help"}}}))
    dataset_id = MairaClient("https://maira.test", "p", "a", http=http).create_dataset(
        name="shop-help", idx_column="help_id", tags=["shop"])

    sent = http.requests[0]
    assert (sent["method"], sent["url"]) == ("POST", "https://maira.test/v1/gpt/datasets")
    assert sent["json"]["idx_column_name"] == "help_id" and sent["json"]["tags"] == ["shop"]
    assert dataset_id == "d-77"


def test_download_image_fetches_the_picture_without_our_keys():
    response = FakeResponse(200)
    response.content = b"\x89PNG"
    response.headers = {"Content-Type": "image/png; charset=binary"}
    http = FakeHttp(response)

    image = MairaClient("https://maira.test", "p", "a", http=http).download_image("https://bucket.test/gen_1.png?sig=x")

    assert image.content == b"\x89PNG" and image.mimetype == "image/png" and image.filename == "gen_1.png"
    assert "headers" not in http.requests[0]  # the storage link is not Maira: keys stay with us
