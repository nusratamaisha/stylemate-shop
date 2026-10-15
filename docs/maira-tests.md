# Maira Test Results: Closet Corner (formerly The House of "M")

Setup on Oct 6: own Maira project (Nusrat — Beta), dataset `house-of-m-products` (10 products, trained), stylist profile with strict mode, Hybrid search and Dataset Tags Includes `house-of-m`.

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

## Tests for the current catalogue (written Oct 13, not yet run)

The catalogue was replaced on Oct 13 with 26 products, SR-017 to SR-042, so the Oct 6 questions below name products that no longer exist. These are the same checks rewritten for the current products.

Before running them:

1. Upload `data/products_sample.csv` from the owner Products tab and wait for training.
2. In the Maira console, delete the old documents `SR-001` to `SR-010` from the product dataset. An upload replaces and adds documents but never removes one, so without this step the assistant keeps recommending clothes the shop no longer has.
3. Run `uv run flask sync-help` so the assistant knows the return and payment rules.

Tests 10 and 11 check the order line from profile rule 7.

| # | Question | Expected behaviour | Answer | Pass? | Top score | Prompt tokens |
|---|---|---|---|---|---|---|
| 1 | I need something for Eid. What do you have under 3,000 taka? | Recommends up to three **festive** pieces priced under ৳3,000, each with price and sizes (for example the Agni Ombre Tiered Maxi Dress at ৳2,950). Offers nothing over budget and invents nothing. The shop has no wedding-guest occasion since Oct 14. | | | | |
| 2 | Is the Akash shirt dress in stock? | Says the **Akash Striped Ruffle Shirt Dress is out of stock** and suggests another office piece, likely the **Mishti Check Kurti Dress** (৳1,750). | | | | |
| 3 | What's good to wear in hot weather? | Suggests up to three cotton pieces, such as the **Nilima Bow-Print Flutter Top**, **Bokul Floral Collared Maxi Dress** or **Mishti Check Kurti Dress**, each with price and sizes. | | | | |
| 4 | Do you sell shoes? | **Refuses to guess:** says the store doesn't sell shoes and names no made-up products. | | | | |
| 5 | Dress in red color in size M | There is no plain red dress. Should offer the **Agni Ombre Tiered Maxi Dress** (orange shading into red, ৳2,950) or the **Dalim Ruffle-Sleeve Dress** (maroon, ৳1,900), saying what colour each really is. May mention the red Lali Lace Tiered Skirt, but must say it is a skirt. | | | | |
| 6 | What is your return policy? | Answers from the Help page FAQ (the `house-of-m-help` dataset): no returns or exchanges; for a wrong size, measure the piece, send a photo and the shop sorts it out. On Oct 6 this was a refusal, because the FAQ wasn't in Maira yet. | | | | |
| 7 | Can I get the Agni maxi with short sleeves? How much extra would it cost? | Says the **Agni Ombre Tiered Maxi Dress is customizable** and **quotes no price**. Ends with `[CUSTOMIZE product_id=SR-018; sleeves=Short; ...]` (rule 8). | | | | |
| 10 | I'd like to order the Maya Gingham Tiered Dress in size M. | One short confirming sentence, then a last line `[ORDER product_id=SR-017; size=M; colour=Black and White Check; quantity=1]`. Asks for no name, phone or address. | | | | |
| 11 | I'd like to order the Akash Striped Ruffle Shirt Dress in size L. | Says it is out of stock and writes **no** `[ORDER ...]` line. | | | | |
| 12 | How can I pay? | Cash on delivery, or bKash, Nagad or Rocket with the transaction ID entered at checkout. Does not ask for a payment itself. | | | | |

## Tests (Oct 6, the first ten-product catalogue)

| # | Question | Expected behaviour | Answer | Pass? | Own data only? | Top score | Prompt tokens |
|---|---|---|---|---|---|---|---|
| 1 | I'm going to a wedding next week. What do you have under 4,500 taka? | Recommends the **Shefali Embroidered Maxi** (৳4,200, sizes S, M, L). Invents nothing else. | Recommended the Shefali Embroidered Maxi at ৳4,200, maroon or emerald, sizes S/M/L, in stock. Added that it has no delivery-time information and suggested contacting the shop. | ✅ (bonus: didn't guess delivery time) | ✅ all 10 from `c1fef7d8-...` | 42.53 (Shefali) | 1,662 |
| 2 | Is the Nira shirt dress in stock? | Says it's **out of stock** and suggests another office dress, likely the **Rumi Wrap Midi Dress** (৳2,450). | "No, the Nira Shirt Dress is out of stock. For an in-stock office dress, the Rumi Wrap Midi Dress is available." | ✅ rules · ⚠️ style: no price or sizes for the Rumi | only dataset | not recorded | not recorded |
| 3 | What's good to wear in hot weather? | Suggests breathable pieces: **Bela Tiered Sundress** (cotton voile), **Kaya Linen Co-ord Set** or **Rumi Wrap Midi Dress** (cotton-linen). | Listed exactly those three, each with fabric, colours, sizes and price, and said all are in stock. | ✅ | only dataset | not recorded | not recorded |
| 4 | Do you sell shoes? | **Refuses to guess:** says the store doesn't sell shoes and names no made-up products. | "No, The House of "M" doesn't sell shoes." | ✅ | only dataset | 23.66 (all 10 between 19.17 and 23.66) | 1,648 |
| 5 | Dress in red color in size M *(the voice transcription)* | Says there's **no red**. Ideally suggests the **Shefali maxi in maroon**, available in M. | not run (Oct 6) | | | | |
| 6 | What is your return policy? | Says it **doesn't have that information** and suggests contacting the shop. Invents no rules. | "I don't have information about The House of "M"'s return policy. Please contact the shop for details." | ✅ | only dataset | not recorded | not recorded |
| 7 | Can I get the Shefali maxi with shorter sleeves? How much extra would it cost? | Says it **is customizable**, but **quotes no price**: the shop calculates that. | Said the Shefali is customizable, that it has no price for the change because the shop calculates custom costs separately, and suggested asking the shop for a quote. | ✅ | only dataset | not recorded | not recorded |

## Follow-up memory test

**Not run on Oct 6.** It will be tested in code on Day 3, when Flask starts storing `session_id`.

Tests whether sending `session_id` back lets the assistant remember the conversation.

| Step | Request | Expected | Answer | Pass? |
|---|---|---|---|---|
| 8a | "Do you have a dress for the office?" (no `session_id`) | Recommends one or two office dresses. Copy `detail.session_id` from the response. | | |
| 8b | "Does it come in XXL?" with `"session_id": "<from 8a>"` added to the body | Answers about **the dress it just recommended**, not a different one | | |
| 8c | Same as 8b but **without** `session_id` | Probably doesn't know what "it" means. This shows whether `session_id` is what carries the memory. | | |

## Tag filter test (multi-shop)

**Not run on Oct 6.** Run it before the Week 2 mentor review, since the multi-shop pitch depends on it.

Checks that a shop's profile can't see another shop's data. This is the core of the multi-shop design.

1. In Maira Datasets, create a dataset named `test-other-shop-products` with tag **`other-shop`** (not `house-of-m`) and ID column `product_id`. Upload `data/test_other_shop.csv` (one shoe product) and train it.
2. Ask the Closet Corner stylist profile the question below.
3. Afterwards, delete the `test-other-shop-products` dataset.

| # | Question | Expected | Answer | Pass? | Any `OS-001` in references? |
|---|---|---|---|---|---|
| 9 | Do you sell shoes? | **Still refuses.** The shoe exists in the project, but in a dataset without the `house-of-m` tag, so the profile must not see it. | | | |

If it recommends the Trail Running Shoes, the tag filter isn't working, and shops could see each other's products.

## Findings

- **Test 1:** every reference came from our dataset. This doesn't prove the tag filter works yet, because ours is the only dataset in the project. Test 9 checks it properly.
- **The whole catalog is sent every time.** All 10 products came back as references (about 100 to 120 tokens each), so prompt tokens only fell from 2,049 to 1,662. With 60 products, Search Max Token will cap how many are sent. Lowering it is a cost lever to test in Week 3.
- **Scores:** the right product scored 42.53. This morning's irrelevant math data scored about 23 to 24. Compare with the refusal tests (4 and 6) before choosing a threshold for "unanswered question".
- **Answers contain Markdown** (`**bold**`, blank lines). The chat widget must render Markdown safely, or the customer will see the asterisks.
- **Response time:** 4.3 s for this answer.
- **Style rule followed unevenly:** test 3 gave price and sizes for every product, but test 2 named the Rumi without them. Short yes/no questions seem to get shorter answers. Week 3 tuning: make the price-and-sizes rule stronger, or decide it's acceptable for stock questions.

- **Scores separate "found it" from "not in the data" (early sign):** test 1 had a clear winner at 42.53, with the rest spread down to 26.51. Test 4 (shoes) had no winner: all 10 products fell between 19.17 and 23.66. Two signals for the owner dashboard's "unanswered questions": a low top score (under about 30) and a flat spread. Confirm with test 6 and the 40 to 60 product catalog before choosing a number. Hybrid scores may not compare perfectly across very different questions.
- **A sturdier option for later:** profiles support `response_format: json_object`. The assistant could return `{"answer": "...", "answered": false}`, giving Flask a clear flag instead of guessing from scores or wording. Consider it in Week 3 or 4 if score thresholds prove unreliable.
- **Customization rule held (test 7):** it confirmed the Shefali is customizable and quoted no price. Once the Week 4 customization panel exists, change rule 5 so it points customers to the panel instead of "contact the shop".
- **Refusals are cheap and fast:** test 4 used only 17 completion tokens and 2.5 s.
- **Shop name:** on Oct 6 the brand was The House of "M", with quotes around the M, which is why the recorded answers use it. It became Closet Corner on Oct 13.

**Summary (Oct 6):** tests 1, 2, 3, 4, 6 and 7 passed. Strict mode held every time: no invented products, policies, delivery times or custom prices. Open: test 5 (voice text), test 8 (memory, moved to Day 3) and test 9 (tag filter, before the Week 2 mentor review).
