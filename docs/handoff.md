# Handoff: Where StyleMate Stands

Last updated: **October 15, 2026**. Update this file at the end of each working session.

## The brief

- Gigalogy internship final project. It must solve a real problem, earn revenue, and use Maira's `ask` endpoint. Chorus (speech-to-text) is an optional extra. Built with Flask and Vue. A strong result could lead to a permanent job.
- **Dates:** feature freeze November 2, buffer November 9-10, deadline **November 10**.
- **Problem:** small online clothing shops lose customers who can't get quick, trustworthy answers about sizes, stock, fabrics and occasions.
- **Revenue idea:** shops pay a monthly plan for StyleMate (three plans, priced from the cost per conversation). One installation serves many shops (`tenant_id` everywhere).

## What happened so far

| Date | What |
|---|---|
| Oct 5-6 | Idea chosen. Maira `ask` and Chorus tested by hand in the sandbox. Stylist profile and `house-of-m-products` dataset (10 products) set up. Day 2 tests 1, 2, 3, 4, 6, 7 passed (`docs/maira-tests.md`). |
| Oct 7 | At Maisha's request, the whole app was built in one go: backend, frontend, 38 tests and `docs/architecture.md`. She is now learning the code from that guide. |
| Oct 11 | Image preview built in one go (journey G in `docs/architecture.md`): backend, product-page panel and 12 tests, 51 in total. Maira's full API spec was found, which settled the upload field name. Maisha's new plan: build everything first, then learn it for the presentation. |
| Oct 11 | Image preview confirmed live with `gpt-image-2` (the first model, `gpt-image-2.5-sunburst`, was refused by the provider). Product specifications added: `length_inches` and `sleeve` columns, which fit the customization menu to each piece. 55 tests. |
| Oct 11 | Size guide added: a page, a pop-up on product pages, and sleeve lengths on the sleeve options. 58 tests. |
| Oct 11 | Product photos added to `data/images/`, and `data/products_sample.csv` rewritten to match them (new names, categories, colours, fabrics, lengths, sleeves, descriptions; same IDs, prices and stock). Tests now use their own fixed catalogue, `backend/tests/data/products.csv`. |
| Oct 11 | Help page added (FAQ, contact details, message form) with a Messages tab in the owner dashboard. 63 tests. |
| Oct 11 | FAQ, size guide and contact details sent to a new Maira dataset (`flask sync-help`); the assistant now answers from them. Daily limits per visitor added for messages and previews. Found and fixed: training straight after an upload trained nothing. 69 tests. |
| Oct 11 | Ordering from the chat built: the assistant proposes an order with a marker line, Flask checks it, and the website opens checkout. Needs profile rule 7 pasted into the Maira console; not yet tried live. 73 tests. |
| Oct 12 | Shop page grouped into sections (Dresses, Tops, Pants and skirts, Sets). Delivery charge added at checkout: ৳80 inside Dhaka, ৳150 outside, set by Flask. 76 tests. |
| Oct 12 | Customer accounts added (sign up, log in, order history) with reviews from customers who ordered the piece. Guest checkout still works. 83 tests. |
| Oct 12 | Each customer's orders numbered from 1; owner login link removed from the storefront; shorter sleeves and length now reduce the price; the notes box explains that measurements need an option. 85 tests. |
| Oct 12 | Made to measure: no S/M/L, measurement boxes, a standard-size suggestion, and a chat hand-off to the product page (needs profile rule 8 pasted; not yet tried live). 90 tests. |
| Oct 12 | Customers can attach a reference picture for the tailor to a made-to-order piece; only the owner can open it. 92 tests. |
| Oct 12 | Owner dashboard: new Orders tab with sales numbers, best sellers and every order (ready-made and made to order), with a status per line. 95 tests. |
| Oct 12 | Ordering a ready-made piece now lowers its stock; the owner can send today's stock to the assistant from the Products tab. 99 tests. |
| Oct 14 | Made to measure simplified: the hip box is gone, only the bust is required, and waist, sleeve length and length are optional. The charge is now ৳300 (was ৳600); the local database was updated by hand. Profile rule 8's `[CUSTOMIZE ...]` line now uses `sleeve_length` instead of `hip`: **re-paste the Introduction from `docs/maira-profile.md` into the Maira console.** The footer credits Daam Koto for the photos; the wedding-guest occasion was removed. 115 tests. |
| Oct 14 | Permission from the Facebook shop page granted. Catalogue grown to **45 products** (15 dresses, 9 tops, 8 pants and skirts, 13 sets): 19 new photos added as SR-043 to SR-061 (originals in `~/Downloads/sample2`; one was a duplicate of SR-057 and was left out). Local database only: **upload `data/products_sample.csv` from the owner Products tab so the assistant knows them.** |
| Oct 14 | Catalogue checked against the photos: SR-049 is now the Surjo Flower-Patch Shirt Top (a top, 30 in), SR-052 renamed Lilac, "Pintuck" and "Ric-Rac" dropped from the SR-038 and SR-044 names, SR-055 now ৳3,500, the wedding-guest occasion removed from SR-039, and customizable switched off for SR-022 and on for SR-025 and SR-059 (18 customizable in all). The picture profile's text in `docs/maira-profile.md` rewritten with honest-fit rules and every console setting. Home page redesigned: a hero with a dress photo, "Shop by section" tiles, New in, and three reasons to shop here. The section list moved to `frontend/src/utils/sections.js` so the home and shop pages agree. |
| Oct 15 | Chat product cards now end with "Click to view more details →" so customers can see they open the product page. 115 tests. |
| Oct 13 | Mentor feedback on image preview, both built: (1) a preview without a customer photo shows **only the garment, no person or face**; (2) a try-on with the customer's photo sends the **chosen size with its size-guide measurements** (or the made-to-measure numbers) and asks for an honest fit. A try-on now needs a size. 114 tests. **Not yet tried against the real image model**, and the picture profile's Introduction in the Maira console must be replaced from `docs/maira-profile.md` (the old text says "one person, standing", which contradicts rule 1). |
| Oct 13 | **Shop renamed to Closet Corner**, with a new logo (a hanger with a gold corner, `BrandMark.vue` and `public/favicon.svg`) and clearer fonts (Poppins for headings, Inter for text, Hind Siliguri kept for Bangla). The header, footer and home page now read the name from the shop's `Tenant` row. Not renamed, on purpose: the slug `house-of-m`, the Maira tag `house_of_m`, the Maira dataset and profile names, the repo and the folder, because the assistant finds its data by that tag. **To do in the Maira console: paste the System and Instructions texts from `docs/maira-profile.md` into both profiles, or the assistant keeps calling the shop The House of "M".** |
| Oct 13 | Payment at checkout: cash on delivery, or bKash, Nagad or Rocket by sending money to the shop's number and typing the transaction ID, which the owner checks and marks as paid in the Orders tab (no gateway; see journey D in `docs/architecture.md`). The Help page message form takes an optional photo, which the owner opens in the Messages tab. 110 tests. **The three wallet numbers are made up (`01700-000000`): put the shop's real ones in `SHOP` in `cli.py` before anyone outside the team uses the site.** The local database got its new columns with a one-off `ALTER TABLE`. |
| Oct 13 | **Catalogue replaced: 26 products, SR-017 to SR-042** (6 dresses, 7 tops, 7 pants and skirts, 6 sets), all with flat-lay photos from one Facebook shop page. Permission was asked for on Oct 13; record the reply in `docs/photo-credits.md` before showing the site outside the team. The Pinterest photos, and a short-lived set of 16 Pexels/Unsplash products (SR-001 to SR-016), were removed; their IDs are not reused. Local database only: the 8 test orders and 1 review on the removed products were deleted with them (backup: `~/Documents/new/stylemate-backup-2026-10-13.db`). **Maira still has the old ten products.** SR-022 has stock 0 for the out-of-stock test. |
| Oct 13 | Help page FAQ now has the shop's own rules: check the parcel in front of the delivery person, no returns or exchanges, a wrong size is fixed after a measured photo. Delivery charges confirmed (৳80 / ৳150). Local only: **run `uv run flask sync-help` so the assistant knows them**. Delivery times, payment and contact details are still sample text. |
| Oct 7-8 | Local setup done: `.env` filled, `.flaskenv` added, `flask seed` run, both servers running. A wrong API key in `.env` (401 "Project credential not found") was fixed. |

## Current state

Working locally:

- `uv run pytest` passes. Seed, backend and frontend run.
- The CSV upload saves products to the local database.

Not yet confirmed against the real APIs:

- [ ] Chat answers in the widget (should work now that the keys are fixed)
- [ ] Voice question through Chorus from the browser mic
- [ ] Follow-up memory with `session_id`: ask "Do you have an office dress?", then "Does it come in XXL?"
- [x] CSV upload reaching the Maira dataset (Oct 12: all 10 new products uploaded from the owner Products tab and trained)
- [x] Image preview against the real image model (Oct 11, `gpt-image-2`). Try-on with a customer photo is still untested.
- [x] Ordering from the chat (Oct 12: rule 7 is in the profile; "I'd like the Kaya Chiffon Midi Dress in size M, navy" produced a valid order line that Flask accepted). Still to do: click through it in the browser, and replace the profile's Instructions text, which still says "I can't place orders"
- [x] The assistant knowing lengths and sleeves (Oct 12: `length_inches` is in the Maira documents)

## CSV upload to Maira: working

- Confirmed live on Oct 12: all 10 new products were uploaded from the owner Products tab and trained, with `length_inches` in the Maira documents.
- Two bugs were fixed on the way. The multipart field is `dataset_file` (the tutorial says `file`), checked by `tests/test_clients.py`. And training must wait until Maira has read the file (`upload_and_train()`).
- **Still to do:** the expected answers in `docs/maira-tests.md` name the old ten products, so re-run them against the new catalogue.
- **Photos:** all from one Facebook shop page since Oct 13, permission pending (`docs/photo-credits.md`). Removed photos are in `~/Documents/new/old_pinterest_photos/` and `~/Documents/new/removed_stock_photos/`; both folders can be deleted.
- **Old documents stay in Maira.** An upload replaces and adds documents but never removes one, so `SR-001` to `SR-010` must be deleted from the product dataset in the Maira console, or the assistant keeps recommending clothes the shop no longer has.
- `~/Documents/new/upload_test.csv` was a one-off price test for the old SR-003 and can be deleted.

## Image preview: working

The panel stays hidden until the shop has an image profile. How it was switched on (repeat for a new shop or a fresh clone):

1. In the Maira console, create a second profile (for example `Closet Corner pictures`) with an image model such as `gpt-image-2`. It needs no dataset tags.
2. Add `MAIRA_IMAGE_PROFILE_ID=<its ID>` to `backend/.env`.
3. From `backend/`, run `uv run flask seed` again. It is safe to repeat and copies the ID onto the shop's row.
4. Restart Flask, open a customizable product, choose a change and press "Show me".
5. Answer the open questions under "Image generation" in `docs/maira-api.md`, then tighten `parse_generated_image()`.

**Oct 11:** switched on. The profile `StyleMate Image` uses `gpt-image-2`; `gpt-image-2.5-sunburst` is listed by Maira but refused by the provider. A dress preview with a typed idea works. Still to try: a preview with a customer photo, and whether the picture link keeps working after a few hours.

The local database got the new `maira_image_profile_id` column on Oct 11 with a one-off `ALTER TABLE`, so it did not need deleting. A fresh clone gets the column from `flask seed` as usual.

## Git

Everything up to October 14 is committed. Check `git status` / `git log origin/main..` for anything not yet pushed. The product photos in `data/images/` are deliberately not in Git (Maisha's decision, Oct 13; `.gitignore` skips them). They stay on this computer, so a fresh clone shows products without pictures until the photos are copied into that folder.

Before any commit, check that `git status` doesn't list `backend/.env` or `backend/stylemate.db`.

## Next steps, in order

1. In the Maira console, paste the stylist profile's Instructions text from `docs/maira-profile.md` (the old text says "I can't place orders"), and check that rule 8 is in the Introduction.
2. Try in the browser: a chat answer, a follow-up ("Do you have an office dress?", then "Does it come in XXL?"), an order from the chat through to checkout, a made-to-measure hand-off (rule 8), a voice question, and a preview with a customer photo.
3. Upload `data/products_sample.csv` (45 products) from the owner Products tab, delete the old documents `SR-001` to `SR-010` in the Maira console, run `uv run flask sync-help`, re-paste the profile Introduction from `docs/maira-profile.md` (its example ID is now SR-018), then run the test sheet in `docs/maira-tests.md`.
4. Learn the code: follow the reading order at the end of `docs/architecture.md`.
5. **Week 2 (Oct 12-18):**
   - Product photos: pick each photo first, then make the product row match it. Save as `data/images/<product_id>.jpg`, about 800 px wide and under 200 KB, from Pexels or Unsplash (not Unsplash+, no logos, not BlueChic).
   - ~~Grow the catalogue to 40-60 products~~ Done Oct 14: 45 products (local; upload to Maira still to do).
   - Test 9 in `docs/maira-tests.md`: a decoy `other-shop` dataset with a shoe, which proves one shop can't see another's data.
   - Show the mentor the working app.
6. **Week 3 (Oct 19-25):**
   - ~~A policies dataset~~ Done Oct 11 as `house-of-m-help` (`flask sync-help`). Return and parcel rules replaced on Oct 13. Still to do: real delivery times, contact details and wallet numbers, then run the command again.
   - Tune the profile: price and sizes in every recommendation; try top_p 0.1-0.3.
   - Tune `UNANSWERED_SCORE_THRESHOLD` using real scores.
   - Try Chorus `initial_prompt` with product names.
   - Test the mic on Chrome, Firefox and a phone.
7. **Week 4 (Oct 26-Nov 1):** fix what real testing finds. Optional extras (photo search, daily summary) only if ahead.
8. **Week 5 (Nov 2-8):**
   - Feature freeze, then a clean-setup test from a fresh clone.
   - Demo script: voice question, one honest refusal, customization with live price, the owner seeing the demand gap.
   - Revenue slide: about 1,650 prompt tokens per question with 10 products.
   - Architecture diagram and a backup screen recording. Rehearse twice.

## Decisions and why

- **Flask in the middle:** it keeps the keys secret, Chorus blocks browsers (CORS), it owns prices, and it logs questions for the dashboard.
- **AI explains, Flask prices:** custom prices are never quoted by the assistant.
- **Multi-shop from the start:** a Tenant row holds each shop's Maira profile and dataset IDs. Profile Dataset Tags keep each assistant inside its own data.
- **Unanswered detection:** the top `similarity_score` is below 30 (configurable).
- **Product cards in chat:** products whose full name appears in the answer.
- **Voice:** the browser records 16 kHz mono WAV itself (`utils/wavRecorder.js`) because browsers default to WebM, which Chorus doesn't accept.
- **SQLite and no migrations:** simplest for a 5-week project (YAGNI).
- **Customization options:** shop-wide rows, not per product.
- **Package name `stylemate`:** it names the platform, not one shop.

## Gotchas already hit

- Run backend commands from `backend/`, because Flask reads `.flaskenv` from the current folder.
- "Address already in use" on port 5000: find the process with `ss -ltnp | grep :5000`.
- `ECONNREFUSED 127.0.0.1:5000` in the Vite terminal means Flask isn't running.
- `http://127.0.0.1:5000/` shows 404 by design; try `/api/shop`.
- Restart Flask after editing `.env`. Debug mode reloads code changes only.
- Check that keys are set without printing them (from `backend/`): `awk -F= '/_KEY=/{print $1, length($2)}' .env`
- Pressing Ctrl+C in the Vite terminal stops the frontend, and the browser then shows "connection refused".
