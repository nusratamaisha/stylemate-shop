# Maira API Notes

## Ask endpoint

`POST https://api.recommender.gigalogy.com/v1/maira/ask`

### Headers

| Header | Purpose |
|---|---|
| `project-key` | Which Gigalogy project the request belongs to |
| `api-key` | Secret key that proves the request is allowed |
| `Content-Type: application/json` | The body is JSON |

Keys live in `.env` only. Never put them in code, screenshots or Git. One pair of keys serves the whole platform; shops are separated by profile and dataset IDs.

### Request

Required: `user_id`, `query`, `conversation_type` (`"chat"` or `"question"`).

```json
{
  "user_id": "test-user-1",
  "query": "do you sell dresses?",
  "conversation_type": "chat",
  "gpt_profile_id": "b787a357-39c8-491d-8465-8893d98a1dc6"
}
```

Optional fields we plan to use:

| Field | Use in StyleMate |
|---|---|
| `gpt_profile_id` | The shop's stylist profile |
| `context_preference.preferred.dataset_id` | Limit search to the shop's dataset |
| `session_id` | Continue a customer's chat (to be tested) |
| `conversation_metadata` | Tag conversations with the shop's `tenant_id` |

### Response (shortened)

```json
{
  "detail": {
    "session_id": "3ce3faaa-...",
    "conversation_id": "a0ce31ac-...",
    "response": "I don't have information about whether The House of \"M\" sells dresses. Please contact the shop to check.",
    "sections": ["227", "447", "..."],
    "references": [
      {
        "section_id": "227",
        "dataset_id": "babf7ac0-...",
        "similarity_score": "24.56",
        "content": "...",
        "tokens": 316
      }
    ],
    "usage": {
      "prompt_tokens": 2049,
      "completion_tokens": 69,
      "total_tokens": 2118
    },
    "gpt_profile_id": "b787a357-...",
    "created_at": "2026-10-06T13:34:27.938476+09:00",
    "run_time": 3.10
  }
}
```

### Fields we use

| Field | What it is | What StyleMate does with it |
|---|---|---|
| `detail.response` | The answer text | Show it in the chat widget |
| `detail.session_id` | ID of the whole chat | Send it back with the next question (to be tested) |
| `detail.conversation_id` | ID of this one question and answer | Store it; probably needed for feedback later |
| `detail.references[].dataset_id` | Which dataset each piece of data came from | Check that answers use only the shop's dataset |
| `detail.references[].similarity_score` | How closely the data matched the question | Possibly detect unanswered questions for the owner dashboard |
| `detail.usage.total_tokens` | Tokens used for this answer | Cost per conversation (revenue slide) |
| `detail.run_time` | Seconds taken | About 3 seconds, so the chat widget needs a loading state |

## Surprises (first test, Oct 6)

1. **Everything is wrapped in `detail`.** Read the answer from `data["detail"]["response"]`, not `data["response"]`.
2. **Search covers every dataset in the project.** With no filter, the first test retrieved Bangla math, chemistry and physics questions from three datasets belonging to another project. Strict mode still refused to guess. **Fixed (Oct 6):** the three foreign datasets were deleted from the project, and the profile now searches only datasets tagged `house-of-m`.
3. **Irrelevant data still costs money.** A 7-token question used 2,049 prompt tokens, almost all from irrelevant retrieved data. Limiting the search cuts cost and improves accuracy.
4. **`similarity_score` is a string** (`"24.56"`). Convert it to a number before comparing.
5. **`created_at` uses UTC+09:00.** Convert to UTC before storing.

## Open questions

- [ ] Does sending `session_id` back give follow-up memory?
- [x] How do we limit a shop's profile to its own data? **Use the profile's Dataset Tags "Includes"**: per the docs, only datasets with those tags are searched. (Whether `context_preference.preferred` restricts or only prioritizes no longer matters.)
- [x] Which Maira project does StyleMate use? **Nusrat — Beta** (project ID `76fcf199-...`), the same project as the first tests. The foreign datasets were deleted on Oct 6.
- [x] What similarity scores do relevant matches get? About 42 for a clear match (wedding, Shefali) and under 24 when the shop doesn't sell the item (shoes). The app uses 30 as the "unanswered" threshold.

## Where the API spec lives

The sandbox page loads its full spec from `https://api.recommender.gigalogy.com/v1/recommender.json`. It opens without keys and lists every endpoint with its fields. Check it before guessing a field name.

## Dataset endpoints (used by the CSV upload, not yet confirmed live)

Field names checked against the spec on Oct 11. Same base URL and keys as `ask`.

| Purpose | Request |
|---|---|
| Upload a CSV (rows with an existing ID replace that document) | `PUT /v1/gpt/datasets/{dataset_id}/file`, multipart form with the file in field `dataset_file` (the tutorial's `file` gives 400 "Either a file or Scrap URLs must be provided") |
| Train after uploading | `POST /v1/gpt/datasets/{dataset_id}/train` with `{"train_type": "text", "batch_size": 1, "only_payload_update": false}` |

## Image generation (used by the picture preview, working since Oct 11)

From the spec, Oct 11. There is no separate image endpoint.

- **How:** `POST /v1/maira/ask` with a profile whose model is an image model. The `query` is the prompt. Our project offers `gpt-image-2`, `gpt-image-2.5-sunburst`, `gpt-image-2.5-flare`, `gemini-3-pro-image` and `gemini-3.1-flash-image`.
- **Reference pictures:** `images`, a list of `{"filename": "me.png", "file_content": "<base64 data URL>"}`. They guide the new picture.
- **Editing an earlier picture:** `"image_generation": {"is_edit": true, "edit_image_url": "<URL from an earlier response>"}`. Not used yet.
- **Response:** the spec says the picture comes back as an S3 URL but doesn't name the field. `parse_generated_image()` searches the whole response for the first image link.

Open questions for the first live call:

- [x] Which response field holds the picture URL? **`detail.generated_images`** (a list). Seen Oct 11, but only empty, so the shape of one entry is still unknown.
- [x] What happens when the image model fails? Maira still answers **200** and puts the reason in `detail.response` as text, for example `Error: Error code: 404 - The model gpt-image-2.5-sunburst does not exist or you do not have access to it`. Nothing is charged (0 tokens). Flask logs that text.
- [x] Which image models does our project have access to? `gpt-image-2` works. `gpt-image-2.5-sunburst` is listed but refused (Oct 11). The others are untried.
- [ ] Does `file_content` want a data URL (`data:image/png;base64,...`) or bare base64? The spec's two examples differ. We send a data URL.
- [ ] Does the URL open in a browser without keys, and for how long? If not, Flask must download the picture and serve it.
- [ ] Does the response also echo the reference pictures' URLs? If so, the search could return the customer's photo by mistake.
- [ ] How long does one picture take, and what does it cost?

## Datasets: things learned on Oct 11

- **Training too early does nothing.** After `PUT .../file`, Maira reads the file in the background (about 2 seconds for 18 rows). A `train` call sent before that finishes returns 202 but trains nothing. The `instant_training` form field did not train either. What works: wait until `documents_count.text_trained` drops below `total`, then call `train` (about 5 seconds for 18 rows). `MairaClient.upload_and_train()` does this.
- **`GET /v1/gpt/datasets/{id}` has its own shape:** `{"response": {"dataset": {...}}}`, with no `detail` wrapper. It includes `tags` and `documents_count` (`total`, `text_trained`).
- **Create:** `POST /v1/gpt/datasets` with `name`, `idx_column_name`, `tags`, `description`. Tags can be changed later with `PUT /v1/gpt/datasets/{id}`.
- **The shop's real tag is `house_of_m`** (underscores), on both the product dataset and the chat profile. Some older notes say `house-of-m`.
- **Help dataset:** `house-of-m-help`, ID `14081c69-6a4b-459e-a3d4-7d7c13d824b6`, 18 rows. With it, "Can I return a customized dress?" scored 66 and "What body size is XL for?" scored 72, both answered correctly.

## IDs (not secret)

| Item | ID |
|---|---|
| Stylist profile | See `maira-profile.md` |
| Dataset | See `maira-dataset.md` |

## Chorus (speech-to-text)

Base URL: `https://api.maira.gigalogy.com/chorus` (different from `ask`). It uses the same `project-key` and `api-key` as `ask`.

Chorus is **asynchronous**: you upload the audio, get a `task_id`, then check back until the text is ready.

### 1. Upload: `POST /v1/speeches`

Body type: `multipart/form-data` (not JSON), because it carries a file.

| Field | Value we use |
|---|---|
| `file` | The recording. WAV is recommended; MP3, OGG, FLAC, M4A and AAC also work. |
| `task_type` | `transcription` |
| `language` | `auto` |

Send only these three fields. Leave out `audio_url`, `num_speakers` and `initial_prompt`.

In Python, don't set the `Content-Type` header yourself. `requests.post(url, files=...)` writes it, including the multipart boundary.

Response (shortened):

```json
{
  "task_id": "4975e0fc-...",
  "status": "queued",
  "message": "Audio queued for processing",
  "language": "auto"
}
```

### 2. Check: `GET /v1/speeches/{task_id}`

Status goes `queued` → `processing` → `completed` (or `failed`).

Response when completed (shortened):

```json
{
  "task_id": "4975e0fc-...",
  "status": "completed",
  "results": {
    "transcription": {
      "text": "Dress in red color in size M",
      "language": { "code": "en", "probability": 0.999 },
      "segments": ["... word timings and probabilities ..."]
    }
  },
  "timings": { "queue_wait": 0.11, "transcription": 1.0 }
}
```

### Fields we use

| Field | What StyleMate does with it |
|---|---|
| `status` | Keep checking until `completed` or `failed` |
| `results.transcription.text` | The customer's question; send it to `ask` |

### Test results (Oct 6)

| Test | Result | Upload to completed |
|---|---|---|
| Music sound effect, 11.7 s MP3 | `""` (no speech found) | 2.2 s |
| Voice, 8 s WAV at CD quality (1.4 MB) | "Dress in red color in size M" | 1.3 s |

### Surprises

1. **Asynchronous.** Flask must check the status in a loop: every second, giving up after about 20 seconds.
2. **The text is at `results.transcription.text`**, not a top-level `transcription` field as the spec suggests.
3. **No speech gives empty text.** Reply "Sorry, I didn't catch that" instead of calling `ask`.
4. **CORS only allows `api.maira.gigalogy.com`.** A browser page can't call Chorus directly; Flask must.
5. **Timestamps are UTC here**, while `ask` used UTC+09:00. Convert everything to UTC before storing.
6. **Gigalogy stores the uploaded audio** (see `input.url`). A real shop should tell customers that voice messages are recorded.
7. **The model is Whisper `large-v3-turbo`.** It supports Bangla, and `initial_prompt` can hint at product names.
8. **Browsers usually record WebM**, which isn't in the supported list. Check this before building the Week 3 mic button.

### Time budget for a voice question

Chorus (about 1.3 to 2.2 s) plus `ask` (about 3.1 s) comes to roughly 5 seconds. The chat widget should show progress, such as "Listening…" then "Thinking…".

### Ideas (not building now)

- Record at 16 kHz mono (`arecord -d 8 -f S16_LE -r 16000 -c 1 question.wav`): about 256 KB instead of 1.4 MB, since Chorus converts to that anyway.
- Pass product names in `initial_prompt` so they're spelled correctly.
- If word probabilities are low, ask the customer to confirm what they said.
