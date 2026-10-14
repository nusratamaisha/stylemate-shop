# Maira Dataset: Closet Corner Products

How the product data is organized in Maira, and why. For a new shop, repeat this with that shop's name and tag.

## How Maira stores a CSV

- **Each CSV row becomes one document.** One product = one document.
- Each document is stored as `column name: value` pairs, and the model reads them that way. Column names must be clear words.
- Every document needs a unique ID (the `idx`). **Uploading a row with an ID that already exists replaces that document.** That makes re-uploading the CSV an update, not a duplicate.
- After upload, the documents must be **trained** (indexed) before search can find them.

## Dataset settings

| Field (API name) | Value | Why |
|---|---|---|
| `name` | `house-of-m-products` | Shop name plus content type, so each shop's datasets are easy to tell apart |
| `description` | `Product catalog for The House of M (sample data)` | For humans browsing the console |
| `idx_column` | `product_id` | Our own stable IDs. Re-uploading the CSV updates products instead of duplicating them. |
| `is_idx_fillup_if_empty` | `false` (the real dataset has `true`, which is harmless while every row has a `product_id`) | A row missing its ID should fail loudly. An auto-filled random ID would create a duplicate product on the next upload. |
| `secondary_idx_column` | empty | Not needed |
| `image_url_column` | empty | This setting is for Maira's image search, which needs public image URLs. Photo search is an optional extra (YAGNI). The `image` column still uploads as ordinary text. |
| `tags` | `house_of_m` | The tag the real dataset carries (underscores, checked in the console on Oct 13). The profile's Includes tag must match it exactly. The shop's tag. The stylist profile includes only this tag, so it can only search this shop's data. |
| `filterable_fields` | empty | The docs don't yet show how `ask` uses them (YAGNI). Adding them later only needs a payload update, not full retraining. |

## The CSV: `data/products_sample.csv`

| Column | Example | Notes |
|---|---|---|
| `product_id` | `SR-001` | Never reuse an ID for a different product |
| `name` | `Rumi Wrap Midi Dress` | |
| `image` | `SR-001.jpg` | Photo filename only, named after the product ID. Flask adds the folder path in one place (DRY), so moving the images never means editing every row. |
| `category` | `Dress` | Dress, Kurti, Bottoms, Top, Co-ord set |
| `occasion` | `Office, Everyday` | Renamed from `mood`: these are occasions, and customers ask "what can I wear to a wedding?" |
| `sizes` | `S, M, L, XL` | |
| `colours` | `Navy, Olive` | |
| `fabric` | `Cotton-linen blend` | |
| `length_inches` | `46` | Optional. Shoulder to hem, a whole number. Lets "Make it yours" show the new length and lets the assistant answer "how long is it?" |
| `sleeve` | `Three-quarter` | Optional. Use the same words as the sleeve options: `Short`, `Full`, `Sleeveless`. The option the piece already has is hidden |
| `price_bdt` | `2450` | A plain number, so Flask can calculate with it later |
| `stock` | `18` | `0` means out of stock |
| `customizable` | `yes` | `yes` or `no` |
| `description` | full sentences | The main text search matches against. Use the words customers use. |

## Product photos

The storefront and chat need a photo for every product. These are served by Flask, not by Maira.

- **Source:** free photos from Pexels or Unsplash. Both allow commercial use without attribution. Don't use Unsplash+ images (paid license), photos with visible brand logos, or BlueChic's photos.
- **Photo first, then data:** pick the photo, then make the product's colours, fabric and description match it. If the assistant says "maroon" and the photo shows blue, the demo looks broken.
- **Files:** name each one after its product ID (`SR-001.jpg`), resize to about 800 px wide, and keep each under about 200 KB for fast pages and a small repo. Store them in `data/images/` for now.
- **After changing descriptions:** re-upload the CSV. Rows with existing IDs replace the old documents, then retrain.

## Training

After uploading, train the dataset for text search:

```
POST /v1/gpt/datasets/{dataset_id}/train
{"train_type": "text", "batch_size": 1, "only_payload_update": false}
```

In the console, use the dataset's Train button if it has one. The dataset should then show 10 documents as **total**, **active** and **text_trained**.

## Future datasets (not now)

When store policies are added in Week 3 (FAQ, shipping, exchanges), put them in a **separate dataset**, such as `house-of-m-policies`, with the same `house_of_m` tag. Products change often and policies rarely, so keeping them apart means re-uploading products can never touch the policies. The shared tag keeps both visible to the shop's profile.

## IDs

| Item | ID |
|---|---|
| Dataset `house-of-m-products` | `c1fef7d8-ab28-4a3b-adb0-79557f497afa` |
