# Maira Test Results: The House of M

Setup: own Maira project (Nusrat — Beta), dataset `house-of-m-products` (10 products, trained), stylist profile with strict mode, Hybrid search and Dataset Tags Includes `house-of-m`.

Endpoint: `POST https://api.recommender.gigalogy.com/v1/maira/ask`

Request body for each test (change only `query`):

```json
{
  "user_id": "test-user-1",
  "query": "<question>",
  "conversation_type": "chat",
  "gpt_profile_id": "<your profile ID>"
}
```

## What to record for every test

- **Answer:** copy the `detail.response` text.
- **Pass?** Did it match the expected behaviour?
- **Own data only?** Is every `references[].dataset_id` your dataset's ID?
- **Top score:** the highest `similarity_score` in `references`.
- **Prompt tokens:** `usage.prompt_tokens`. Compare with 2,049 from the first test in the shared project.

## Tests (Oct 6)

| # | Question | Expected behaviour | Answer | Pass? | Own data only? | Top score | Prompt tokens |
|---|---|---|---|---|---|---|---|
| 1 | I'm going to a wedding next week. What do you have under 4,500 taka? | Recommends the **Shefali Embroidered Maxi** (৳4,200, sizes S, M, L). Invents nothing else. | | | | | |
| 2 | Is the Nira shirt dress in stock? | Says it's **out of stock** and suggests another office dress, likely the **Rumi Wrap Midi Dress** (৳2,450). | | | | | |
| 3 | What's good to wear in hot weather? | Suggests breathable pieces: **Bela Tiered Sundress** (cotton voile), **Kaya Linen Co-ord Set** or **Rumi Wrap Midi Dress** (cotton-linen). | | | | | |
| 4 | Do you sell shoes? | **Refuses to guess:** says the store doesn't sell shoes and names no made-up products. | | | | | |
| 5 | Dress in red color in size M *(the voice transcription)* | Says there's **no red**. Ideally suggests the **Shefali maxi in maroon**, available in M. | | | | | |
| 6 | What is your return policy? | Says it **doesn't have that information** and suggests contacting the shop. Invents no rules. | | | | | |
| 7 | Can I get the Shefali maxi with shorter sleeves? How much extra would it cost? | Says it **is customizable**, but **quotes no price**: the shop calculates that. | | | | | |

## Follow-up memory test

Tests whether sending `session_id` back lets the assistant remember the conversation.

| Step | Request | Expected | Answer | Pass? |
|---|---|---|---|---|
| 8a | "Do you have a dress for the office?" (no `session_id`) | Recommends one or two office dresses. Copy `detail.session_id` from the response. | | |
| 8b | "Does it come in XXL?" with `"session_id": "<from 8a>"` added to the body | Answers about **the dress it just recommended**, not a different one | | |
| 8c | Same as 8b but **without** `session_id` | Probably doesn't know what "it" means. This shows whether `session_id` is what carries the memory. | | |

## Findings

(Fill in after testing: what passed, what failed, the scores of relevant matches compared with refusals, and any profile changes to try.)
