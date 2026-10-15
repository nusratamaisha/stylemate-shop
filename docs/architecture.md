# How StyleMate Works

StyleMate is an AI shopping assistant for online clothing shops. Closet Corner is the first shop on it (it was called The House of "M" until October 13, 2026, which is why its internal ID is still `house-of-m`). This guide explains how the pieces fit together, so you can find your way around the code and explain it in your presentation.

## 1. The big picture

```
 Customer's browser                         Shop owner's browser
 (Vue storefront + chat)                    (Vue dashboard)
          │                                         │
          └──────────────┬──────────────────────────┘
                         │  requests to /api/...
                         ▼
              Flask backend (port 5000)
              ├── SQLite database: shops, products, chats, orders
              ├── Maira ask ........ answers questions from the shop's data
              ├── Maira ask (image profile) ... draws a preview of a customized dress
              ├── Maira datasets ... receives product CSVs and trains on them
              └── Chorus ........... turns voice recordings into text
```

During development, Vue runs on port 5173 and forwards every `/api/...` request to Flask (see `frontend/vite.config.js`). The browser only ever talks to one site.

**Why Flask sits in the middle** (a good presentation point):

1. **Keys stay secret.** The Gigalogy keys live in `backend/.env`. Anything in Vue code can be read by any visitor.
2. **Chorus blocks browsers.** Its CORS policy only allows Gigalogy's own site, so a browser can't call it directly.
3. **Prices are trusted.** Flask calculates every price, including custom changes. The AI explains; Flask decides.
4. **Records are kept.** Every question is saved, which is what powers the owner dashboard.

## 2. Where everything lives

Each file has one job. If you know what you want to change, this table tells you where to look.

### Backend (`backend/stylemate/`)

| File | Its one job |
|---|---|
| `__init__.py` | `create_app()`: builds the app and decides which Maira and Chorus clients to use |
| `config.py` | Reads every setting from `.env` |
| `models.py` | The database tables. Every table has a `tenant_id` |
| `errors.py` | Two error types: bad input (400) and a Gigalogy service failing (502) |
| `cli.py` | `flask seed`: creates the shop, options, size guide, FAQ, products and owner login. `flask sync-help`: sends the FAQ and size guide to Maira |
| `clients/base.py` | Shared HTTP code for Gigalogy: keys, headers and error handling, written once |
| `clients/maira.py` | Asks Maira for answers and for pictures; uploads and trains the dataset; reads the `detail` wrapper |
| `clients/chorus.py` | Uploads audio to Chorus and checks back until the text is ready |
| `services/chat.py` | The assistant: asks Maira, finds the products it mentioned, checks an order it proposes, flags unanswered questions, saves the turn |
| `services/pricing.py` | Custom prices and ready dates |
| `services/accounts.py` | Customer accounts: signing up, logging in, a customer's own order history |
| `services/reviews.py` | Product reviews, allowed only for a customer who ordered the piece |
| `services/help.py` | The Help page: questions and answers, contact details, saving customers' messages, and sending the answers to Maira |
| `services/limits.py` | Daily limits per visitor for contact messages and picture previews |
| `services/uploads.py` | Checks uploaded pictures and keeps customers' pictures (for the tailor, or sent with a message) where only the owner can open them |
| `services/payments.py` | How an order is paid: cash on delivery, or a bKash, Nagad or Rocket transaction ID that the owner checks |
| `services/sizes.py` | The size guide: what body each size fits, and how long each kind of sleeve is |
| `services/preview.py` | Image preview: checks the request, writes the prompt, asks Maira for the picture |
| `services/orders.py` | Checkout and the custom order queue |
| `services/catalog.py` | Reading products and importing a CSV |
| `services/insights.py` | Numbers for the owner dashboard |
| `api/shop.py` | Public routes: products, size guide, help and contact, chat, voice, price quotes, picture previews, orders, images |
| `api/account.py` | Customer routes: sign up, log in, log out, my orders, reviews |
| `api/owner.py` | Owner routes: login, insights, custom orders, CSV upload, customer messages |
| `api/helpers.py` | Finding the current shop, checking the owner is logged in |
| `api/__init__.py` | Registers the routes and turns errors into JSON, in one place |

### Frontend (`frontend/src/`)

| File | Its one job |
|---|---|
| `api.js` | Every call to Flask goes through here, with the same error handling |
| `stores/shop.js` | Loads the shop details and products once, for every page |
| `stores/account.js` | The logged-in customer, shared by every page |
| `stores/sizeGuide.js` | Loads the size guide the first time someone opens it |
| `stores/bag.js` | The shopping bag, saved in the browser |
| `stores/chat.js` | The conversation: sending text or voice, remembering Maira's session |
| `utils/wavRecorder.js` | Records the microphone as a 16 kHz mono WAV (see journey B) |
| `utils/markdown.js` | Turns the assistant's Markdown into safe HTML |
| `utils/colours.js` | Colour names as swatch colours |
| `utils/visitor.js` | The random visitor ID kept in the browser, shared by chat and previews |
| `components/ChatWidget.vue` | The chat on every page (display only; logic is in `stores/chat.js`) |
| `components/CustomizePanel.vue` | "Make it yours": options and the live price from Flask |
| `components/ProductReviews.vue` | Reviews on a product page: the list, the average, and the form for a customer who ordered the piece |
| `components/SizeGuide.vue` | The size guide tables, used on the Size guide page and in the pop-up on a product page |
| `components/PreviewPanel.vue` | "See it first": asks for a picture of the dress with the chosen changes, optionally on the customer's photo |
| `components/ProductImage.vue` | The product photo, or fabric swatches until a photo is added |
| `views/*.vue` | One file per page. `ShopView.vue` groups the collection into sections (Dresses, Tops, Pants and skirts, Sets) by each product's `category` |

## 3. The journeys, step by step

### A. A customer types a question

1. `ChatWidget.vue` calls `chat.ask()` in `stores/chat.js`.
2. `stores/chat.js` sends `POST /api/chat` with the message, a random visitor ID kept in the browser, and Maira's `session_id` from the previous answer, if there is one.
3. `api/shop.py` finds the shop with `current_tenant()` and calls `ChatService.reply()`.
4. `services/chat.py` calls `MairaClient.ask()` with the shop's profile ID (stored on the shop's database row, not in code).
5. `clients/maira.py` sends the request with the keys, unwraps `detail`, and turns `similarity_score` strings into numbers.
6. Back in `services/chat.py`:
   - **Product cards:** products whose full name appears in the answer become cards, in the order mentioned.
   - **Unanswered flag:** if the best `similarity_score` is below 30, the question is marked as not answered by the catalogue. In testing, a real match scored about 42 and "Do you sell shoes?" scored under 24.
   - The question and answer are saved as a `ChatTurn` row.
7. The widget shows the answer (Markdown rendered safely) and the product cards. Each card links to its product page and ends with "Click to view more details →", a call to action that shows customers the card can be clicked.

### A2. A customer orders from the chat

The customer says "I want to order Jui". The stylist asks a few quick questions in the chat (size, colour, and for a customizable piece any changes such as length or sleeves), fills in the order and takes them to checkout. They can also confirm it right there in the chat, the way a shop answers on Messenger.

1. Rule 7 of the Maira profile (`docs/maira-profile.md`) tells the assistant to start the order **as soon as** the customer wants it, with only what it already knows, on a last marker line: `[ORDER product_id=SR-023; size=M; colour=; quantity=1]`. It doesn't ask the questions itself: on Oct 15 the model kept asking "Would you like it in Yellow?" and never wrote the line, so the customer could never order.
2. `read_order()` in `services/chat.py` takes that line out of the answer, so the customer never sees it, and checks it against the database: the product exists in this shop and is in stock. A size or colour the piece doesn't come in is left empty, and a piece with only one size or colour gets it filled in.
3. **Safety net:** if the assistant forgets the line, `order_from_question()` still starts the order when the customer's message asks to order ("order", "buy", "kinbo", "অর্ডার"…) and the answer is about exactly one product.
4. The reply's `order` lists what can still be chosen: `sizes`, `colours`, and `changes` (the product page's menu from `pricing.options_for()`, without made to measure, which needs measurement boxes and stays on the product page, rule 8).
5. `stores/chat.js` asks the missing questions one by one, as stylist messages with tap-to-answer buttons; the rules for which question comes next are in `utils/chatOrder.js`. A typed answer such as "M", "yellow" or "no" is matched to the buttons and **not** sent to Maira, so the questions cost no AI calls and can't loop.
6. When nothing is missing, `ChatOrderCard.vue` shows the order with its price. With changes, the price and the ready date come from `POST /api/price-quote` (`pricing.py`), never from the browser. Then:
   - **"Go to checkout"** puts the piece in the bag, with its changes, and opens `/bag`.
   - **"Or confirm here in the chat"** opens a small form in the chat (delivery area, payment, name, phone, address) and sends it to the same `POST /api/orders` with `source: "chat"`.
   - **"Change my answers"** asks the questions again.
7. Either way, `orders.place_order()` checks and prices the order exactly as in journey D. A chat-confirmed order has `Order.source = "chat"`, which the owner sees as a **Chat** badge in the Orders tab and `sales_summary()` counts as `chat_orders`.

The checkout fields live in `CheckoutFields.vue`, shared by the checkout page and the chat card (DRY: pulled out when the chat became the second place to order).

**Why a marker and not "let the AI place the order":** the assistant only *proposes*. It can't create an order, set a price or skip the stock check, because Flask does those. A wrong or invented marker is refused. The delivery details are typed into a form, even inside the chat, not written to the assistant, so a phone number or address never passes through Maira and can't be misread by it. Changes chosen in the chat are priced by `pricing.py` like on the product page; only made to measure stays on the product page.

### B. A customer asks by voice

1. `ChatWidget.vue` starts `wavRecorder.js`. Browsers normally record WebM, which Chorus doesn't accept, so the recorder captures raw sound and packs it as a **16 kHz mono WAV**, the format Chorus converts everything to anyway. Eight seconds is about 256 KB.
2. Recording stops when the customer taps Send, or after 15 seconds.
3. `stores/chat.js` sends the file to `POST /api/voice`.
4. `clients/chorus.py` uploads it, gets a `task_id`, then checks every second until the status is `completed`, giving up after 20 seconds.
5. If no speech was heard, the customer sees "Sorry, I didn't catch that", and Maira is never called, so no cost.
6. Otherwise the text goes through journey A, marked as voice. The customer sees what was heard, then the answer.

### C. A customer customizes a dress

1. `ProductView.vue` loads `GET /api/products/SR-002`. For customizable products, the response includes the shop's options grouped by Sleeves, Length, Lining and Fit.
2. Each choice in `CustomizePanel.vue` sends `POST /api/price-quote` with the option IDs.
3. `services/pricing.py` checks the product is customizable, allows one option per group, refuses an option the piece already has, adds the extra prices, and works out the ready date (7 days plus each option's extra days).
4. The panel shows the breakdown. The customer adds the custom piece to the bag.

Options are database rows (`CustomizationOption`), not code. A shop adds a new option by adding a row.

**How the customer knows what they are changing.** A change like "Shorter by 2 inches" means nothing without a starting point, so each product can carry two specifications from the CSV: `length_inches` (shoulder to hem) and `sleeve` ("Full", "Three-quarter", "Sleeveless"...). `pricing.options_for()` uses them to fit the shop-wide menu to the product:

- Each group shows what the piece is like now: "Sleeves, now: Full", "Length, now: 56 in".
- The option the piece already has is left out, so a full-sleeved dress doesn't offer "Full sleeves" for +৳200. `calculate_quote()` refuses it too, so checkout can't be tricked into charging for it.
- Length options show the result: "Shorter by 2 inches (54 in)". The same text goes into the order, so the tailor reads the final length.
- The image preview tells the model what the piece is like as sold, so it changes the right thing.

**The size guide** answers the two questions a number alone can't: "what body is an XL for?" and "how long is a short sleeve?". It is two small tables per shop, `SizeGuideRow` (bust, waist and hip for each size) and `SleeveLength` (inches for each kind of sleeve), filled with starting values by `flask seed`. `GET /api/size-guide` returns both. The customer meets it in three places: the "Size guide" page in the top menu, a "Size guide" link beside the size choice that opens a pop-up showing only that product's sizes, and the sleeve options themselves, which read "Short sleeves (about 7 in)". It is rows, not code, for the same reason as the options: another shop cuts its sizes differently.

**A change can lower the price.** Short sleeves, sleeveless and a shorter length use less fabric, so their rows hold a negative amount (−৳100, −৳150, −৳100) and the panel shows them in green. They are still made to order, so the ready date still applies.

**Made to measure needs no S, M or L.** The Fit option "Made to your measurements" is marked `needs_measurements`. Choosing it swaps the size buttons for four number boxes (only the bust is required; waist, sleeve length and length are optional, because not every piece needs them), and hides the "2 inches shorter/longer" options, because the piece is cut to the exact length typed. `orders.py` then stores the size as "Made to measure" and writes the checked measurements into the order for the tailor. The panel also compares the measurements with the size guide: if a standard size already fits within 2 inches, it says so and offers to order that size and save the ৳300 charge. A changed length or sleeve length can only be sewn to order, so then it doesn't offer a standard size. A shop that tells customers when they don't need the paid option earns trust.

**From the chat.** If a customer says "Shefali, sleeveless, length 36, bust 38", profile rule 8 makes the assistant end its answer with `[CUSTOMIZE product_id=SR-002; sleeves=Sleeveless; bust=38; length=36]`. `read_customize()` in `services/chat.py` keeps only what the shop can make (a sleeve this piece offers, measurements within the ranges in `pricing.MEASUREMENTS`) and the chat shows a "See the price and finish" button. It opens the product page with those choices filled in. The chat never prices a custom piece: the product page does, through `pricing.py`.

**A reference picture for the tailor.** Under the notes box a customer can attach a photo or sketch. It is uploaded as soon as it is chosen (`POST /api/reference-pictures`), because the bag lives in the browser and can't hold a file. Flask checks the type and size, saves it in `backend/uploads/` under a random name, and returns that name; the order line then carries it. At checkout `orders.py` accepts the name only if that file really exists and the line is made to order, so a made-up name is ignored. The picture is opened through an owner-only route (`/api/owner/custom-orders/<id>/reference-picture`), and the owner sees a thumbnail in the custom order queue. Uploads are limited per visitor per day like messages and previews.

**Typed measurements never change the price.** The price comes only from the options chosen. If a customer types measurements without choosing an option, the panel says the note won't be sent and offers "Made to your measurements" (+৳600) in one click. Without an option the order is a standard-size piece at the listed price.

Both columns are optional. A product without them keeps the full menu and simply can't show results. The sleeve match compares words, so the CSV must use the same words as the option labels ("Short" for "Short sleeves").

### D. Checkout

1. `BagView.vue` shows the two delivery areas and their charges, which come from `GET /api/shop` (৳80 inside Dhaka, ৳150 outside). The customer picks one and sees subtotal, delivery and total.
2. It sends `POST /api/orders` with the customer's details, the **delivery area**, and each line's product, size, colour, quantity, options and notes. **Prices and the delivery charge are not sent.**
3. `services/orders.py` checks every size and colour exists, recalculates every price with `pricing.py`, looks up the delivery charge for the chosen area with `pricing.shipping_charge()`, and checks stock for ready-made pieces. The charge is once per order, not per piece, and is saved on the order with the area. Custom pieces are made to order, so an out-of-stock dress can still be ordered with changes.
4. **Stock goes down.** `_take_from_stock()` adds up the ready-made lines per product (stock is per product, so one in each colour counts as two), refuses the whole order if any piece is short ("only 6 left"), and otherwise lowers each product's stock. Everything is saved in one commit, so a refused order changes nothing. Made-to-order lines are sewn for the customer and use no stock.
5. Custom lines get status `new` and a ready date, and appear in the owner's custom order queue.

The two charges are fields on the shop's `Tenant` row, so another shop can charge differently without a code change. The customer chooses the area themselves; the address is free text, so Flask can't check that it matches.

**Paying.** The customer chooses cash on delivery, bKash, Nagad or Rocket. The list comes from `GET /api/shop`, built by `services/payments.py` from three wallet numbers on the shop's `Tenant` row; a wallet without a number isn't offered.

1. For a wallet, `BagView.vue` shows the shop's number and the total, and asks for the **transaction ID (TrxID)** from the wallet's confirmation message. The customer sends the money in their own wallet app.
2. `payments.check_payment()` tidies the ID (no spaces, capitals), refuses one that isn't 6 to 20 letters and numbers, and refuses one already used for another order of this shop. The order is saved with `payment_status` `to_check`. A cash order is `unpaid`.
3. In the dashboard's **Orders** tab the owner sees the method and the TrxID, compares it with the wallet's history, and presses "Mark as paid" (`PATCH /api/owner/orders/<id>/payment`). A number at the top counts the payments still to check.

**No money moves through this app, and there is no payment gateway.** A gateway (bKash Checkout, Nagad, or an aggregator such as SSLCommerz) needs a registered merchant account with business documents, and approval takes longer than this project. Sending money and quoting the TrxID is how many small online shops in Bangladesh really take wallet payments, so this is the shop's real process, not a mock. If the shop gets a merchant account, only `payments.py` changes: `check_payment()` would ask the provider instead of waiting for the owner.

**What it can't do:** it can't tell a real TrxID from a made-up one. That is the owner's check, which is why a wallet order starts as `to_check` and not `paid`.

### E. The owner uploads products

1. The Products tab sends a CSV to `POST /api/owner/products/upload`.
2. `services/catalog.py` checks every row and lists all problems at once, like "Row 3: price_bdt must be a whole number".
3. Valid rows are saved: an existing `product_id` updates that product, and a new one adds a product.
4. The **same file** goes to the shop's Maira dataset. Flask then waits until Maira has read the file (about 2 seconds) before it starts training, because a train call sent too early trains nothing (`MairaClient.upload_and_train()`). Maira also replaces documents with matching IDs, so one file keeps the website and the assistant in step.
5. If Maira fails, the products are still saved, and the owner is told the assistant wasn't updated.

### F. The owner dashboard

The dashboard opens on the **Orders** tab (`GET /api/owner/orders`). `orders.sales_summary()` gives the numbers an owner checks first: how many orders (and how many were confirmed in the chat), sales in taka (with delivery money shown apart, because it is collected, not earned), pieces sold and how many were made to order, lines still to ship, and the five best sellers. Below them, `orders.all_orders()` lists **every** order, ready-made and made to order, with the customer's name, phone, address and delivery area, and a status for each line. The **Custom orders** tab is the tailor's queue: the same made-to-order lines, with their changes, measurements and reference pictures.

For the **Customer questions** tab, `services/insights.py` reads the shop's `ChatTurn` rows and returns:

- how many questions were asked, the share answered from the catalogue, and how many came by voice;
- the most asked questions (grouped so "Do you sell shoes?" and "do you sell shoes" count together);
- **questions the catalogue couldn't answer**: the demand gaps, which show the owner what customers want that the shop doesn't sell;
- recent conversations.

### G. A customer previews a dress as a picture

This covers two wishes with one flow. "Show me this dress with my changes" draws **the piece on its own, with no person and no face**. "Show me wearing it" (the customer adds a photo) draws **the size they chose on their real body**. Both rules came from the mentor review on October 13.

1. `GET /api/products/SR-002` includes `preview_available`. It is true only when the shop has an image profile, so `ProductView.vue` shows `PreviewPanel.vue` only then.
2. The panel sends `POST /api/products/SR-002/preview` as a form: the colour, the option IDs chosen in "Make it yours", an optional typed idea (up to 200 characters), and an optional photo of the customer.
3. `services/preview.py` refuses bad requests **before** any paid call: no image profile, an idea for a dress that can't be customized, a colour the dress doesn't come in, a file that isn't a JPG, PNG or WebP under 4 MB, or nothing to show at all.
4. The option IDs go through `pricing.quote_for()`, the same function that prices the order. So the picture can only show options the shop really sells, one per group, and the words in the prompt ("Sleeves: Short sleeves") are the same words the order will carry.
5. `build_prompt()` writes the instruction from the product's own data (name, category, colour, fabric, description), then the changes, then the typed idea. Without a customer photo it asks for a product photo of the garment alone and forbids a person, face, hands or body: an invented model would distract from the changes and could look like a real person.
   - **With a customer photo, the fit is added.** `fit_description()` takes the size chosen on the page and looks it up in the shop's size guide, so the prompt says, for example, "size M, cut for a bust of 36 inches, a waist of 30 inches and a hip of 39 inches", and tells the model to show that size honestly: tight if too small, loose if too large, never reshaping the person. A try-on without a size is refused before the paid call. A made-to-measure piece has no S, M or L, so the prompt gives the customer's own measurements and says it fits exactly.
   - **What this can't promise:** the image model sees a photo, not a tape measure, so the fit in the picture is an impression, not a measurement. The caption already says the finished piece may look different.
6. Reference pictures go along with the prompt: the customer's photo first, then the shop's photo of the dress if `data/images/` has one. The prompt says which is which.
7. `MairaClient.generate_image()` sends it to `/v1/maira/ask`, the same endpoint as chat. Maira draws instead of writing because the **image profile's model is an image model**. It waits up to 120 seconds, not the usual 30.
8. Maira returns a link to the picture. The panel shows it with a note that it is AI-drawn and that the price above is what the customer pays.

**Why it is built this way** (presentation points):

- **A picture never sets a price.** A typed idea like "a gold border" appears in the picture only. To order it, the customer writes it in the notes and the shop confirms. This keeps the rule "the AI explains, Flask decides".
- **The customer's photo is not stored.** Flask passes it to Maira and keeps no copy. The panel says so.
- **Each shop pays for its own pictures.** The image profile ID is on the `Tenant` row, like the chat profile. A shop without one simply doesn't show the panel.

### I. A customer logs in, sees their orders and writes a review

1. "Log in" in the top menu opens `AccountView.vue`. A new customer signs up with a name, email and password (at least 8 characters); `POST /api/account/register` saves a `Customer` row with the password **hashed**, never as typed, and logs them in.
2. Logging in sets `customer_id` in the signed session cookie. Every page asks `GET /api/account/me` once, which answers the customer or `null` for a guest.
3. At checkout, `POST /api/orders` links the order to the logged-in customer (`Order.customer_id`). A guest can still order; that order belongs to no account. This also keeps ordering from the chat working without a login.
4. The account page lists the customer's orders from `GET /api/account/orders`, newest first, with each made-to-order piece's status. **Each customer's orders are numbered from 1** (`customer_order_number`), so a customer never sees gaps left by other people's orders. The shop-wide ID is shown beside it as "Ref #", because that is the number the owner searches by. The query filters by the customer's own ID, so nobody can read another person's orders.
5. Each product page shows its reviews and the average (`GET /api/products/<code>/reviews`). The form appears only for a logged-in customer **who has ordered that piece** (`reviews.has_ordered()`), and each customer gets one review per product: writing again replaces it. Reviews show the first name only.

**Owner and customer logins are separate on purpose.** The storefront has no link to the owner login: the owner opens `/owner/login` directly. Hiding the link is tidiness, not security; what protects the dashboard is `owner_required`. They are two tables (`User` and `Customer`) and two session keys (`user_id` and `customer_id`). `owner_required` only ever looks at `user_id`, so a customer account can never open the dashboard, and a test checks exactly that.

**Why only buyers can review:** a review from someone who never bought the piece tells the next customer nothing, and it is the cheapest protection against fake reviews.

### H. A customer needs help

1. "Help" in the top menu opens `HelpView.vue`, which loads `GET /api/help`: the shop's questions and answers (`FaqItem` rows) and its contact details (four fields on the `Tenant` row).
2. The contact form sends `POST /api/contact` with a name, a phone number or email, a message and an **optional photo** (for example a wrong size laid flat with a measuring tape on it). `services/help.py` refuses a message with no way to reply, then saves it as a `ContactMessage` row. The photo is checked and saved by `services/uploads.py` under a random name in `backend/uploads/`, the same way as a reference picture for the tailor.
3. The owner reads the messages in the dashboard's **Messages** tab (`GET /api/owner/messages`, owner login required), opens a photo with `GET /api/owner/messages/<id>/picture`, and replies by phone or email.

4. **Daily limits.** One visitor can send 5 messages a day and ask for 20 picture previews a day (`CONTACT_MESSAGES_PER_DAY` and `PREVIEWS_PER_DAY` in `.env`; 0 switches a limit off). `services/limits.py` counts uses in a `RateLimitEvent` table and answers 429 when the limit is reached. A request refused for another reason (an empty name, a wrong file type) is not counted, and a preview is counted only just before the paid call. The visitor is recognised by a **hash of their IP address**: the browser's visitor ID would be useless here because anyone can clear it, and hashing means the address itself is never stored.
5. **The assistant knows the same answers.** `uv run flask sync-help` turns the FAQ, the size guide and the contact details into question-and-answer rows and sends them to a second Maira dataset, `house-of-m-help`. It copies the product dataset's tag, and the chat profile searches by tag, so the assistant finds the new dataset with no change to the profile. Each row has a stable ID (`FAQ-2`, `SIZE-XL`), so running the command again replaces answers instead of duplicating them. Run it after changing the FAQ or size guide.

**Who can read messages.** Only the shop owner. Every `/api/owner/...` route except login is wrapped in `owner_required`, which checks the owner's session, so a customer's browser can't read questions, orders or messages (customer accounts are journey I).

**Why it is built this way:** the chat answers only from the catalogue, so it needs somewhere to send people when it can't answer. The FAQ covers the predictable questions for free (no Maira call), and the form catches the rest. Messages are stored, not emailed, because the app has no email service and the owner already has a dashboard.

## 4. How it serves many shops

- Every table has a `tenant_id`, and every query filters by it.
- Each shop's Maira profile ID and dataset ID live on its `Tenant` row. The profile's Dataset Tags keep each shop's assistant inside its own data.
- The storefront finds its shop in one function, `current_tenant()` in `api/helpers.py`. Today it reads `SHOP_SLUG` from `.env`. To host many shops from one deployment, only that function changes, for example to read the subdomain.
- The owner side uses the logged-in owner's shop, so one owner can never see another shop's questions or orders.

## 5. Where SOLID, DRY and YAGNI show up

| Principle | Example in the code |
|---|---|
| **Single responsibility** | Clients only talk HTTP, services only hold business rules, routes only handle web requests. `ChatWidget.vue` displays; `stores/chat.js` decides. |
| **Open/closed** | New customization options are database rows. A new shop is a new `Tenant` row. Neither needs code changes. |
| **Liskov substitution** | `tests/fakes.py` has a `FakeMaira` and `FakeChorus` with the same methods as the real clients. The app works identically with either. |
| **Interface segregation** | `ChatService` needs only an object with `ask()`, and `PreviewService` only one with `generate_image()`. Neither knows about datasets or training. |
| **Dependency inversion** | `create_app(maira=..., chorus=...)` lets tests pass in the fakes. The services receive their client; they never create it. |
| **DRY** | Keys and headers: once, in `clients/base.py`. Errors into JSON: once, in `api/__init__.py`. Prices: only `pricing.py`, which the image preview also uses to check options. One CSV feeds both the database and Maira. |
| **YAGNI** | No payment gateway (the owner checks transaction IDs by hand), no migrations tool, no per-product option menus, no image search. SQLite instead of a database server. Each would be added only when needed. |

## 6. Tests

Run them from `backend/`:

```bash
uv run pytest
```

There are 123 tests. They use the fake clients, so they need no keys, cost nothing and run in seconds. They cover response parsing (including the `detail` wrapper and string scores), Chorus polling and timeouts, pricing rules, checkout that ignores tampered prices, the unanswered flag, the owner login wall, CSV import errors, and the image preview (the prompt, the order of reference pictures, and every refusal).

## 7. Known limits and next steps

| Limit | What to do |
|---|---|
| The dataset upload (`PUT /v1/gpt/datasets/{id}/file`, file field `dataset_file`) now matches Maira's API spec but hasn't been confirmed live | Upload a CSV from the Products tab once, then check the Documents list in the Maira console |
| Image preview has never run against the real API. Where the picture link sits in the response, and whether the link opens in a browser without keys, are unknown | Create an image profile, set `MAIRA_IMAGE_PROFILE_ID`, re-seed, try one preview, then tighten `parse_generated_image()` to the real field |
| A try-on picture is the model's impression, not a fitting | Keep the "AI-drawn preview" note; never promise fit from it |
| Whether `session_id` gives follow-up memory hasn't been confirmed | Ask "Do you have an office dress?", then "Does it come in XXL?" in the chat |
| The unanswered threshold (30) comes from two test questions | Watch the scores as real questions come in, and adjust `UNANSWERED_SCORE_THRESHOLD` |
| Orders lower stock in the database at once, but Maira only knows the stock it was last sent | Press "Send today's stock to the stylist" in the Products tab. The website stays correct either way: product pages, chat cards and chat orders all check the database |
| Uploading a products CSV sets stock to the numbers in the file, undoing what orders took off | Put today's stock in the CSV before uploading it |
| Stock is one number per product, not per size and colour | Fine for a demo; a real shop needs stock per size and colour |
| Stock in Maira is a snapshot from the last CSV upload | Re-upload the CSV after stock changes |
| Products removed from the CSV stay in the database and in Maira | Delete them in the Maira console for now |
| An option has one price for every product. "Short sleeves" is −৳100 even on a sleeveless piece, where it would add fabric | No customizable piece is sleeveless today; price by direction (compare sleeve lengths) if one is added |
| Customization options are shop-wide; only the sleeve and length options adapt to the product | Fine for one shop; make them per product only if a shop needs it |
| The lengths and sleeves in `data/products_sample.csv` are sample values, not measured | Replace them with real measurements when the photos are chosen |
| One length per product, though real length varies a little by size | Add a length per size only if customers ask |
| The size guide numbers are common starting values, not the shop's own, and the owner can't edit them from the dashboard | Replace the values in `cli.py` (`DEFAULT_SIZES`, `DEFAULT_SLEEVE_LENGTHS`) before seeding; add an owner screen if a second shop joins |
| The assistant learns FAQ and size guide changes only when `flask sync-help` is run | Run it after every change; make it automatic if the owner gets an FAQ editor |
| Daily limits count by IP address, so people sharing one connection share a limit, and during local development every visitor is 127.0.0.1 | Raise the limits in `.env` for a demo; behind a proxy, pass the visitor's real address through |
| The FAQ answers and contact details are partly sample text (delivery times, a made-up phone and address, and **made-up bKash, Nagad and Rocket numbers**). The return rule, the parcel check, the delivery charges and the payment methods are the shop's own since Oct 13 | Replace them in `cli.py` (`DEFAULT_FAQ`, `SHOP`) with the shop's real ones |
| The owner can't edit the FAQ or mark messages as answered | Add when a real shop needs it |
| A reference picture uploaded for a piece that is never ordered stays in `backend/uploads/` | Delete files older than a few days that no order points to |
| Accounts have no password reset, no email confirmation and no limit on wrong password attempts | Needs an email service; add before real customers use it |
| The owner can't see, hide or answer reviews | Add a Reviews tab to the dashboard if a shop needs moderation |
| Orders placed as a guest are not attached to an account created later | Fine for a demo |
| No migrations: tables are created on startup | If you change `models.py`, delete `backend/stylemate.db` and run `flask seed` again |
| Placeholder swatches instead of photos | Add photos to `data/images/`, named like the CSV `image` column (`SR-001.jpg`) |
| Profile rule 5 says "contact the shop" for custom prices | Change it to point customers to the "Make it yours" section on the product page (see `maira-profile.md`) |

## 8. A reading order for learning the code

1. `backend/stylemate/__init__.py`: how the app is assembled.
2. `backend/stylemate/models.py`: what is stored.
3. `backend/stylemate/clients/maira.py`, then `chorus.py`: the APIs you tested by hand on Day 1, now in code.
4. `backend/stylemate/services/chat.py`: the heart of the assistant.
5. `backend/stylemate/api/shop.py`: how a request reaches a service.
6. `backend/tests/test_chat.py`: the same behaviour, written as checks.
7. `frontend/src/stores/chat.js`, then `components/ChatWidget.vue`: the other end of the conversation.
8. `backend/stylemate/services/pricing.py` with `frontend/src/components/CustomizePanel.vue`: journey C from both sides.
9. `backend/stylemate/services/preview.py`, `backend/tests/test_preview.py`, then `frontend/src/components/PreviewPanel.vue`: journey G.
