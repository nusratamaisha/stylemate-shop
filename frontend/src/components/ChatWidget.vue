<script setup>
// The stylist chat, on every page. Displays the conversation from stores/chat.js
// and handles typing and the microphone.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ProductImage from './ProductImage.vue'
import { useBag } from '../stores/bag.js'
import { useChat } from '../stores/chat.js'
import { renderMarkdown } from '../utils/markdown.js'
import { formatTaka } from '../utils/format.js'
import { canRecord, startRecording } from '../utils/wavRecorder.js'

const MAX_RECORDING_SECONDS = 15
const SUGGESTIONS = [
  'I need something for Eid. What do you have under ৳3,000?',
  'Can I get a dress with long sleeves?',
]

const chat = useChat()
const bag = useBag()
const router = useRouter()

// The customer confirmed an order in the chat and Flask checked it. The answer shows a
// "Go to checkout" link; pressing it puts the piece in the bag and opens the checkout page.
// The customer described a made-for-them piece in the chat. Open its page with those
// choices filled in; the price and the rest of the measurements are settled there.
function goToCustomize(message) {
  const { product, sleeves, measurements } = message.customize
  chat.state.open = false
  router.push({ path: `/products/${product.code}`, query: { ...(sleeves ? { sleeves } : {}), ...measurements } })
}
const describeCustomize = ({ sleeves, measurements }) =>
  [sleeves, ...Object.entries(measurements).map(([name, inches]) => `${name.replace('_', ' ')} ${inches} in`)].filter(Boolean).join(' · ')

function goToCheckout(message) {
  const order = message.order
  if (!message.inBag) {
    bag.add({
      product_code: order.product.code,
      name: order.product.name,
      image_url: order.product.image_url,
      colours: order.product.colours,
      size: order.size,
      colour: order.colour,
      quantity: order.quantity,
      option_ids: [],
      custom_details: '',
      notes: '',
      unit_price_bdt: order.unit_price_bdt,
    })
    message.inBag = true // pressing the link again must not add a second one
  }
  chat.state.open = false // so the checkout form isn't hidden behind the chat
  router.push('/bag')
}

const draft = ref('')
const log = ref(null)
const input = ref(null)
const micAvailable = canRecord()

const recording = ref(null) // the active recorder, or null
const seconds = ref(0)
let timer = null

const busy = computed(() => chat.state.status !== 'idle')
const statusText = computed(() => ({
  thinking: 'The stylist is thinking…',
  transcribing: 'Listening to your question…',
}[chat.state.status] || ''))

function toggle() {
  chat.state.open = !chat.state.open
  if (chat.state.open) nextTick(() => input.value?.focus())
}

function send(text = draft.value) {
  if (!text.trim() || busy.value) return
  chat.ask(text)
  draft.value = ''
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

async function startMic() {
  try {
    recording.value = await startRecording()
  } catch (error) {
    chat.notice(error?.name === 'NotAllowedError'
      ? 'Microphone access is blocked. Allow it in your browser’s site settings, or type your question.'
      : 'The microphone couldn’t start. Please type your question instead.')
    return
  }
  seconds.value = 0
  timer = setInterval(() => {
    seconds.value += 1
    if (seconds.value >= MAX_RECORDING_SECONDS) stopMic()
  }, 1000)
}

async function stopMic() {
  const recorder = recording.value
  if (!recorder) return
  clearInterval(timer)
  recording.value = null
  const wav = await recorder.stop()
  chat.askByVoice(wav)
}

function cancelMic() {
  clearInterval(timer)
  recording.value?.cancel()
  recording.value = null
}

onBeforeUnmount(cancelMic)

watch(
  () => [chat.state.messages.length, chat.state.status],
  () => nextTick(() => log.value?.scrollTo({ top: log.value.scrollHeight, behavior: 'smooth' })),
)
</script>

<template>
  <div class="chat">
    <button
      v-if="!chat.state.open"
      class="launcher"
      type="button"
      aria-label="Ask our stylist"
      @click="toggle"
    >
      <span class="launcher-quote" aria-hidden="true">“ ”</span>
      <span class="launcher-text">Ask our stylist</span>
    </button>

    <section v-else class="panel" aria-label="Chat with our stylist">
      <header class="panel-head">
        <div>
          <h2 class="panel-title">Ask our stylist</h2>
          <p class="panel-sub">Answers come only from this shop’s catalogue.</p>
        </div>
        <button class="close" type="button" aria-label="Close chat" @click="toggle">×</button>
      </header>

      <div ref="log" class="log" aria-live="polite">
        <div v-if="!chat.state.messages.length" class="welcome">
          <p>Hi! Ask me about sizes, colours, fabrics, prices, or what to wear for an occasion. You can type or tap the microphone.</p>
          <div class="suggestions">
            <button v-for="text in SUGGESTIONS" :key="text" class="suggestion" type="button" @click="send(text)">
              {{ text }}
            </button>
          </div>
        </div>

        <template v-for="(message, index) in chat.state.messages" :key="index">
          <p v-if="message.role === 'notice'" class="notice">{{ message.text }}</p>

          <div v-else-if="message.role === 'customer'" class="bubble customer">
            <p>{{ message.text }}</p>
            <span v-if="message.viaVoice" class="spoken">Spoken</span>
          </div>

          <div v-else class="bubble stylist">
            <div class="answer" v-html="renderMarkdown(message.text)"></div>
            <div v-if="message.order" class="order">
              <p class="order-summary">
                <strong>{{ message.order.product.name }}</strong><br />
                Size {{ message.order.size }}, {{ message.order.colour }}<span v-if="message.order.quantity > 1">, {{ message.order.quantity }} pieces</span>
                · {{ formatTaka(message.order.unit_price_bdt * message.order.quantity) }}
              </p>
              <button type="button" class="button small" @click="goToCheckout(message)">
                {{ message.inBag ? 'Back to checkout' : 'Go to checkout' }}
              </button>
              <p class="order-note">You’ll add your name, phone and address there.</p>
            </div>
            <div v-else-if="message.customize" class="order">
              <p class="order-summary">
                <strong>{{ message.customize.product.name }}</strong>, made for you<br />
                {{ describeCustomize(message.customize) }}
              </p>
              <button type="button" class="button small" @click="goToCustomize(message)">See the price and finish</button>
              <p class="order-note">Your choices will be filled in on the product page.</p>
            </div>
            <div v-else-if="message.products?.length" class="cards">
              <RouterLink
                v-for="product in message.products"
                :key="product.code"
                :to="`/products/${product.code}`"
                class="card"
              >
                <ProductImage :product="product" class="thumb" />
                <span class="card-text">
                  <span class="card-name">{{ product.name }}</span>
                  <span class="card-price">{{ formatTaka(product.price_bdt) }}</span>
                  <span v-if="!product.in_stock" class="tag out">Out of stock</span>
                  <!-- The whole card is the link; this line tells customers so -->
                  <span class="card-cta">Click to view more details →</span>
                </span>
              </RouterLink>
            </div>
          </div>
        </template>

        <p v-if="statusText" class="status">{{ statusText }}</p>
      </div>

      <div v-if="recording" class="composer recording">
        <span class="dot" aria-hidden="true"></span>
        <span class="rec-text">Listening… 0:{{ String(seconds).padStart(2, '0') }}</span>
        <button class="text-button" type="button" @click="cancelMic">Cancel</button>
        <button class="button small" type="button" @click="stopMic">Send</button>
      </div>

      <form v-else class="composer" @submit.prevent="send()">
        <label class="visually-hidden" for="chat-input">Your question</label>
        <textarea
          id="chat-input"
          ref="input"
          v-model="draft"
          rows="1"
          maxlength="500"
          placeholder="Type your question"
          :disabled="busy"
          @keydown="onKeydown"
        ></textarea>
        <button
          v-if="micAvailable"
          class="icon-button"
          type="button"
          aria-label="Ask by voice"
          :disabled="busy"
          @click="startMic"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z"/>
          </svg>
        </button>
        <button class="button small" type="submit" :disabled="busy || !draft.trim()">Send</button>
      </form>
    </section>
  </div>
</template>

<style scoped>
.launcher {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 56px;
  padding: 0 22px 0 18px;
  border: 0;
  border-radius: 999px;
  background: var(--sindoor);
  color: #fff;
  font: 600 1rem / 1 var(--font-body);
  box-shadow: 0 8px 24px rgba(92, 21, 32, 0.28);
  cursor: pointer;
}
.launcher:hover { background: var(--sindoor-deep); }
.launcher-quote {
  font-family: var(--font-display);
  font-size: 1.75rem;
  line-height: 0.6;
  padding-top: 8px;
  color: #f3d58c;
}

.panel {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 40;
  display: flex;
  flex-direction: column;
  width: min(400px, calc(100vw - 40px));
  height: min(620px, calc(100vh - 40px));
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 18px 48px rgba(43, 32, 36, 0.18);
  overflow: hidden;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 18px 14px;
  border-bottom: 1px solid var(--line);
  background: var(--sindoor);
  color: #fff;
}
.panel-title {
  font-size: 1.375rem;
  margin: 0;
  color: #fff;
}
.panel-sub {
  margin: 2px 0 0;
  font-size: var(--step--1);
  color: #f2dfe1;
}
.close {
  border: 0;
  background: none;
  color: #fff;
  font-size: 1.75rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 4px;
}

.log {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.welcome p { margin-bottom: 12px; }
.suggestions { display: flex; flex-direction: column; gap: 8px; }
.suggestion {
  text-align: left;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--jamdani);
  color: var(--kohl);
  font: inherit;
  font-size: var(--step--1);
  cursor: pointer;
}
.suggestion:hover { border-color: var(--sindoor); }

.bubble { max-width: 88%; }
.bubble p { margin: 0; }
.customer {
  align-self: flex-end;
  padding: 10px 14px;
  border-radius: 14px 14px 4px 14px;
  background: var(--indigo);
  color: #fff;
}
.spoken {
  display: block;
  margin-top: 2px;
  font-size: 0.75rem;
  color: #c9d2ea;
  text-align: right;
}
.stylist {
  align-self: flex-start;
  padding: 10px 14px 12px;
  border-radius: 14px 14px 14px 4px;
  background: var(--jamdani);
}
.answer :deep(p) { margin: 0 0 0.6em; }
.answer :deep(p:last-child) { margin-bottom: 0; }
.answer :deep(ul),
.answer :deep(ol) { margin: 0.3em 0 0.6em; padding-left: 1.2em; }
.answer :deep(strong) { color: var(--sindoor-deep); }

.cards { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; }
.card {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 6px;
  border-radius: 8px;
  background: #fff;
  color: inherit;
  text-decoration: none;
  border: 1px solid var(--line);
}
.card:hover { border-color: var(--sindoor); }
.thumb { width: 44px; flex: none; border-radius: 4px; }
.card-text { display: flex; flex-direction: column; line-height: 1.3; }
.card-name { font-weight: 600; font-size: var(--step--1); }
.card-price { color: var(--muted); font-size: var(--step--1); }
.card-cta { margin-top: 2px; color: var(--sindoor-deep); font-size: var(--step--1); font-weight: 600; }
.card:hover .card-cta { text-decoration: underline; }

.order {
  margin-top: 10px;
  padding: 12px;
  border-radius: var(--radius);
  background: #fff;
  border: 1px solid var(--line);
}
.order-summary {
  margin: 0 0 10px;
}
.order-note {
  margin: 8px 0 0;
  font-size: var(--step--1);
  color: var(--muted);
}
.notice {
  align-self: center;
  margin: 0;
  max-width: 90%;
  text-align: center;
  font-size: var(--step--1);
  color: var(--muted);
}
.status {
  margin: 0;
  font-size: var(--step--1);
  color: var(--muted);
  font-style: italic;
}

.composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--line);
}
.composer textarea {
  resize: none;
  min-height: 44px;
  max-height: 120px;
}
.icon-button {
  flex: none;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: #fff;
  color: var(--sindoor);
  cursor: pointer;
}
.icon-button:hover { border-color: var(--sindoor); }
.icon-button:disabled { opacity: 0.5; cursor: not-allowed; }
.composer .button { flex: none; min-height: 44px; }

.recording { align-items: center; }
.rec-text { flex: 1; font-weight: 500; }
.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--danger);
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  50% { opacity: 0.3; }
}

@media (max-width: 520px) {
  .panel {
    right: 0;
    bottom: 0;
    width: 100vw;
    height: 100dvh;
    border-radius: 0;
  }
  .launcher { right: 16px; bottom: 16px; }
}
</style>
