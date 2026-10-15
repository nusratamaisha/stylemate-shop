<script setup>
// StyleMate's own public page: how a Facebook clothing shop learns what StyleMate does,
// sees the plans and asks for a demo. Not part of any shop, so App.vue shows it without
// the shop's header, footer and chat. Plans and prices come from Flask (services/plans.py).
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api.js'
import { formatTaka } from '../utils/format.js'

const plans = ref([])
const pricesAreExamples = ref(false)
onMounted(async () => {
  try {
    const data = await api('/plans')
    plans.value = data.plans
    pricesAreExamples.value = data.prices_are_examples
  } catch {
    plans.value = [] // the rest of the page still works; the form still sends
  }
})

const FEATURES = [
  ['An AI stylist that never sleeps', 'Answers size, fabric, colour and price questions in Bangla or English, day and night, only from your own catalogue, so it never makes things up.'],
  ['Orders inside the chat', 'The stylist asks for the size and colour, then the customer confirms the order without leaving the chat.'],
  ['Made to measure, priced for you', 'Customers type their measurements and see the exact price for longer sleeves or a different length, worked out by your own rules.'],
  ['Voice questions', 'Customers who would rather speak can ask out loud, the way they send voice messages on Messenger.'],
  ['See it before you buy', 'A picture preview of the piece with the customer’s changes, or on their own photo in the size they chose.'],
  ['Pay the way Bangladesh pays', 'Cash on delivery, or bKash, Nagad and Rocket with a transaction ID you check. No gateway fees.'],
  ['Know what customers want', 'Your dashboard shows every order and every question, including the ones your shop couldn’t answer, so you know what to stock next.'],
  ['Suggestions that fit', '“You may also like” and “Complete the look”, only with pieces in stock and in the customer’s size.'],
]

const form = reactive({ shop_name: '', owner_name: '', phone: '', facebook_page: '', product_count: '', plan: '', message: '' })
const sending = ref(false)
const sent = ref(false)
const error = ref('')
const formSection = ref(null)

function choosePlan(key) {
  form.plan = key
  formSection.value?.scrollIntoView({ behavior: 'smooth' })
}

async function send() {
  sending.value = true
  error.value = ''
  try {
    await api('/demo-requests', { method: 'POST', body: { ...form } })
    sent.value = true
  } catch (err) {
    error.value = err.message
  } finally {
    sending.value = false
  }
}

const planLines = (plan) => [
  `${plan.chat_questions.toLocaleString('en-IN')} AI chat questions a month`,
  plan.voice ? 'Voice questions' : null,
  plan.previews ? `${plan.previews.toLocaleString('en-IN')} picture previews a month` : null,
  plan.smart_recommendations ? 'Smart suggestions (Gigalogy)' : 'Suggestions from your own catalogue',
  plan.products ? `Up to ${plan.products} products` : 'Unlimited products',
].filter(Boolean)
const POPULAR = 'growth' // the plan marked "Most shops choose this"
</script>

<template>
  <div class="stylemate">
    <header class="top">
      <div class="wrap bar">
        <a href="#top" class="logo" aria-label="StyleMate, top of page">Style<span>Mate</span></a>
        <nav class="links" aria-label="StyleMate">
          <a href="#how">How it works</a>
          <a href="#pricing">Pricing</a>
          <RouterLink to="/">See a live shop</RouterLink>
        </nav>
        <a href="#demo" class="cta small-cta">Request a demo</a>
      </div>
    </header>

    <main id="top">
      <section class="hero wrap">
        <p class="eyebrow">For clothing shops that sell on Facebook</p>
        <h1>Your customers ask on Messenger. Who answers at midnight?</h1>
        <p class="lead">
          StyleMate gives your Facebook shop its own website with an AI stylist. It answers questions about sizes,
          fabrics and prices from your own catalogue, takes orders in the chat, and works out custom prices,
          so no customer leaves because nobody replied.
        </p>
        <div class="actions">
          <a href="#demo" class="cta">Request a demo</a>
          <RouterLink to="/" class="ghost">See a live shop: Closet Corner →</RouterLink>
        </div>
      </section>

      <section id="how" class="band">
        <div class="wrap">
          <h2>How it works</h2>
          <ol class="steps">
            <li><strong>Send us your products.</strong> A spreadsheet of names, sizes, colours and prices, plus your photos.</li>
            <li><strong>We set up your shop.</strong> Your own website, with a stylist that knows only your catalogue and your rules.</li>
            <li><strong>Share the link on your page.</strong> Customers ask, customize and order. You see every order and every question in your dashboard.</li>
          </ol>
        </div>
      </section>

      <section class="wrap features" aria-labelledby="features-title">
        <h2 id="features-title">What your shop gets</h2>
        <div class="grid">
          <article v-for="[title, text] in FEATURES" :key="title" class="feature">
            <h3>{{ title }}</h3>
            <p>{{ text }}</p>
          </article>
        </div>
      </section>

      <section id="pricing" class="band">
        <div class="wrap">
          <h2>Pricing</h2>
          <p class="sub">One monthly price. Every plan includes your shop website, orders, cash on delivery and mobile wallets, and the owner dashboard.</p>
          <div class="plans">
            <article v-for="plan in plans" :key="plan.key" class="plan" :class="{ popular: plan.key === POPULAR }">
              <p v-if="plan.key === POPULAR" class="badge">Most shops choose this</p>
              <h3>{{ plan.name }}</h3>
              <p class="price"><strong>{{ formatTaka(plan.price_bdt) }}</strong> <span>a month</span></p>
              <p class="pitch">{{ plan.pitch }}</p>
              <ul>
                <li v-for="line in planLines(plan)" :key="line">{{ line }}</li>
              </ul>
              <button type="button" class="cta full" @click="choosePlan(plan.key)">Ask about {{ plan.name }}</button>
            </article>
          </div>
          <p class="fine">
            If a busy month uses up your questions, your stylist keeps answering for another 10% while we let you know,
            so customers are never cut off suddenly. Your dashboard warns you at 80%.
            <template v-if="pricesAreExamples"><br /><strong>Prices shown are examples while we finalise them.</strong></template>
          </p>
        </div>
      </section>

      <section id="demo" ref="formSection" class="wrap demo" aria-labelledby="demo-title">
        <h2 id="demo-title">Request a demo</h2>
        <p class="sub">Tell us about your shop. We’ll call you, show StyleMate with your own products, and set it up with you.</p>

        <div v-if="sent" class="thanks" role="status">
          <h3>Thank you, {{ form.owner_name }}!</h3>
          <p>We’ll call you on {{ form.phone }} soon to arrange your demo.</p>
        </div>

        <form v-else class="form" @submit.prevent="send">
          <div class="two">
            <div class="field">
              <label for="demo-shop">Shop name</label>
              <input id="demo-shop" v-model="form.shop_name" maxlength="120" required />
            </div>
            <div class="field">
              <label for="demo-name">Your name</label>
              <input id="demo-name" v-model="form.owner_name" autocomplete="name" maxlength="120" required />
            </div>
            <div class="field">
              <label for="demo-phone">Phone number</label>
              <input id="demo-phone" v-model="form.phone" type="tel" autocomplete="tel" maxlength="40" required />
            </div>
            <div class="field">
              <label for="demo-page">Facebook page link <span class="muted">(optional)</span></label>
              <input id="demo-page" v-model="form.facebook_page" type="url" maxlength="300" placeholder="https://facebook.com/yourshop" />
            </div>
            <div class="field">
              <label for="demo-products">How many products? <span class="muted">(optional)</span></label>
              <select id="demo-products" v-model="form.product_count">
                <option value="">Not sure</option>
                <option>Under 50</option>
                <option>50 to 200</option>
                <option>Over 200</option>
              </select>
            </div>
            <div class="field">
              <label for="demo-plan">Plan you’re interested in <span class="muted">(optional)</span></label>
              <select id="demo-plan" v-model="form.plan">
                <option value="">Not sure yet</option>
                <option v-for="plan in plans" :key="plan.key" :value="plan.key">{{ plan.name }}</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label for="demo-message">Anything else? <span class="muted">(optional)</span></label>
            <textarea id="demo-message" v-model="form.message" rows="3" maxlength="1000"
              placeholder="For example: we sell kurtis and three-piece sets, mostly made to order"></textarea>
          </div>
          <p v-if="error" class="message error" role="alert">{{ error }}</p>
          <button type="submit" class="cta" :disabled="sending">{{ sending ? 'Sending…' : 'Request my demo' }}</button>
        </form>
      </section>
    </main>

    <footer class="foot">
      <div class="wrap">
        <p><strong>StyleMate</strong>: AI shop websites for clothing sellers in Bangladesh. AI answers by Gigalogy’s Maira.</p>
        <p class="muted"><RouterLink to="/">Closet Corner</RouterLink> is a demo shop with sample data.</p>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* StyleMate's own look: indigo rather than the demo shop's maroon, so the platform and a shop don't blur */
.stylemate {
  --accent: var(--indigo);
  --accent-wash: var(--indigo-wash);
  background: var(--paper);
  color: var(--kohl);
  min-height: 100vh;
}
.wrap {
  width: min(100% - 2 * var(--gutter), var(--max));
  margin-inline: auto;
}
.top {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(253, 251, 249, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
}
.bar {
  display: flex;
  align-items: center;
  gap: 24px;
  min-height: 64px;
}
.logo {
  font-family: var(--font-display);
  font-size: 1.375rem;
  font-weight: 700;
  color: var(--kohl);
  text-decoration: none;
}
.logo span {
  color: var(--accent);
}
.links {
  display: flex;
  gap: 20px;
  margin-left: auto;
}
.links a {
  color: var(--kohl);
  text-decoration: none;
  font-weight: 500;
}
.links a:hover {
  color: var(--accent);
}
.cta {
  display: inline-block;
  padding: 12px 22px;
  border: 0;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition: transform var(--ease), box-shadow var(--ease);
}
.cta:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow);
}
.cta:disabled {
  opacity: 0.6;
}
.small-cta {
  padding: 9px 16px;
  font-size: var(--step--1);
}
.full {
  width: 100%;
}
.ghost {
  color: var(--accent);
  font-weight: 600;
}
.hero {
  padding: clamp(48px, 9vw, 112px) 0 clamp(40px, 7vw, 88px);
}
.hero > * {
  max-width: 860px; /* a readable line length, on the same left edge as the sections below */
}
.eyebrow {
  color: var(--accent);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: var(--step--1);
}
.hero h1 {
  font-size: clamp(2rem, 5vw, var(--step-4));
  line-height: 1.12;
  margin: 8px 0 20px;
}
.lead {
  font-size: var(--step-1);
  line-height: 1.55;
  color: var(--muted);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 20px;
  margin-top: 28px;
}
.band {
  background: var(--accent-wash);
  padding: clamp(40px, 7vw, 80px) 0;
}
h2 {
  font-size: var(--step-3);
  margin: 0 0 12px;
}
.sub {
  color: var(--muted);
  max-width: 680px;
  margin: 0 0 28px;
}
.steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  padding: 0;
  margin: 24px 0 0;
  list-style: none;
  counter-reset: step;
}
.steps li {
  counter-increment: step;
  padding: 24px;
  border-radius: var(--radius-large);
  background: #fff;
  line-height: 1.5;
}
.steps li::before {
  content: counter(step);
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  margin-bottom: 12px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
}
.features {
  padding: clamp(40px, 7vw, 80px) 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-top: 24px;
}
.feature {
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius-large);
  background: #fff;
}
.feature h3 {
  font-size: var(--step-0);
  margin: 0 0 8px;
}
.feature p {
  margin: 0;
  color: var(--muted);
  font-size: var(--step--1);
  line-height: 1.55;
}
.plans {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  align-items: stretch;
}
.plan {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 28px 24px;
  border: 1px solid var(--line);
  border-radius: var(--radius-large);
  background: #fff;
}
.plan.popular {
  border: 2px solid var(--accent);
  box-shadow: var(--shadow);
}
.badge {
  position: absolute;
  top: -13px;
  left: 24px;
  margin: 0;
  padding: 3px 12px;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 600;
}
.plan h3 {
  margin: 0;
  font-size: var(--step-1);
}
.price {
  margin: 8px 0 4px;
}
.price strong {
  font-family: var(--font-display);
  font-size: var(--step-3);
}
.price span,
.pitch {
  color: var(--muted);
}
.pitch {
  font-size: var(--step--1);
  min-height: 3em;
}
.plan ul {
  flex: 1;
  margin: 8px 0 24px;
  padding: 0;
  list-style: none;
}
.plan li {
  padding: 7px 0 7px 26px;
  border-top: 1px solid var(--line);
  position: relative;
  font-size: var(--step--1);
}
.plan li::before {
  content: '✓';
  position: absolute;
  left: 4px;
  color: var(--accent);
  font-weight: 700;
}
.fine {
  margin-top: 24px;
  color: var(--muted);
  font-size: var(--step--1);
}
.demo {
  padding: clamp(40px, 7vw, 80px) 0;
  max-width: 820px;
}
.two {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0 20px;
}
.thanks {
  padding: 24px;
  border-radius: var(--radius-large);
  background: #e9f3ee;
}
.thanks h3 {
  margin: 0 0 6px;
}
.foot {
  padding: 32px 0;
  border-top: 1px solid var(--line);
  font-size: var(--step--1);
}
.foot p {
  margin: 4px 0;
}
@media (max-width: 960px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .plans,
  .steps {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .links {
    display: none;
  }
  .small-cta {
    margin-left: auto;
  }
  .grid,
  .two {
    grid-template-columns: 1fr;
  }
}
</style>
