<script setup>
// The stylist chat, on every page. Displays the conversation from stores/chat.js
// and handles typing and the microphone.
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChatOrderCard from './ChatOrderCard.vue'
import ProductImage from './ProductImage.vue'
import { useBag } from '../stores/bag.js'
import { useChat } from '../stores/chat.js'
import { useShop } from '../stores/shop.js'
import { renderMarkdown } from '../utils/markdown.js'
import { formatDate, formatTaka } from '../utils/format.js'
import { canRecord, startRecording } from '../utils/wavRecorder.js'

const MAX_RECORDING_SECONDS = 15
const SUGGESTIONS = [
  'I need something for Eid. What do you have under ৳3,000?',
  'Can I get a dress with long sleeves?',
]

const chat = useChat()
const bag = useBag()
const router = useRouter()

// The customer described a made-for-them piece in the chat. Open its page with those
// choices filled in; the price and the rest of the measurements are settled there.
function goToCustomize(message) {
  const { product, sleeves, measurements } = message.customize
  chat.state.open = false
  router.push({ path: `/products/${product.code}`, query: { ...(sleeves ? { sleeves } : {}), ...measurements } })
}
const describeCustomize = ({ sleeves, measurements }) =>
  [sleeves, ...Object.entries(measurements).map(([name, inches]) => `${name.replace('_', ' ')} ${inches} in`)].filter(Boolean).join(' · ')

// An order started in the chat: once the stylist's questions are answered, ChatOrderCard shows the
// summary. Its "Go to checkout" lands here: the piece goes in the bag and the checkout page opens.
function goToCheckout(message, item) {
  if (!message.inBag) {
    bag.add(item)
    message.inBag = true // pressing the link again must not add a second one
  }
  chat.state.open = false // so the checkout form isn't hidden behind the chat
  router.push('/bag')
}

const draft = ref('')
const log = ref(null)
const input = ref(null)
const shop = useShop()
// The browser can record, and the shop's plan includes voice questions (services/plans.py)
const micAvailable = computed(() => canRecord() && shop.info?.features?.voice !== false)

const recording = ref(null) // the active recorder, or null
const seconds = ref(0)
let timer = null

const busy = computed(() => chat.state.status !== 'idle')
const statusText = computed(() => ({
  thinking: 'The stylist is thinking…',
  transcribing: 'Listening to your question…',
}[chat.state.status] || ''))

// Deleting can't be undone, so it asks first
function deletePastChat(id) {
  if (window.confirm('Delete this chat? It will be removed from your past chats.')) chat.deletePastChat(id)
}

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
  () => [chat.state.messages.length, chat.state.status, chat.state.view], // also on coming back from the list
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
        <div class="head-actions">
          <template v-if="chat.state.view === 'chat'">
            <button class="head-button" type="button" @click="chat.showPastChats()">Past chats</button>
            <button v-if="chat.state.messages.length" class="head-button" type="button" :disabled="busy"
              @click="chat.newChat()">New chat</button>
          </template>
          <button v-else class="head-button" type="button" @click="chat.backToChat()">← Back</button>
          <!-- Only hides the panel: the chat goes on (checkout closes it too) -->
          <button class="close" type="button" aria-label="Close chat" @click="toggle">×</button>
        </div>
      </header>

      <p v-if="chat.state.historyError" class="history-error" role="alert">{{ chat.state.historyError }}</p>

      <!-- The list of past chats (stores/chat.js, utils/chatStorage.js) -->
      <div v-if="chat.state.view === 'past'" class="log">
        <p v-if="!chat.state.pastChats.length" class="notice">
          No past chats yet. Press “New chat” and the chat you’re in will be kept here.
        </p>
        <p v-else class="notice">Open a chat to carry on where you left off. The chat you’re in now will be kept here.</p>
        <div v-for="past in chat.state.pastChats" :key="past.id" class="past-chat">
          <button type="button" class="past-open" :disabled="busy" @click="chat.openPastChat(past.id)">
            <span class="past-title">{{ past.title }}</span>
            <span class="past-date">{{ formatDate(past.ended_at) }}</span>
          </button>
          <button type="button" class="past-delete" :aria-label="`Delete the chat “${past.title}”`"
            @click="deletePastChat(past.id)">Delete</button>
        </div>
      </div>

      <template v-else>

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

          <div v-else class="bubble stylist" :class="{ wide: message.draftId && !message.question }">
            <div class="answer" v-html="renderMarkdown(message.text)"></div>
            <!-- A follow-up question for an order: tap an answer, or type it -->
            <div v-if="message.question" class="choices" role="group" :aria-label="message.text">
              <button v-for="choice in message.question.choices" :key="String(choice.value)" type="button" class="choice"
                :class="{ picked: message.answered === choice.label }" :disabled="message.answered !== null"
                @click="chat.answer(message, choice)">
                {{ choice.label }}<span v-if="choice.note" class="choice-note"> {{ choice.note }}</span>
              </button>
            </div>
            <ChatOrderCard v-else-if="message.draftId" :draft="chat.state.drafts[message.draftId]" :in-bag="message.inBag"
              @checkout="(item) => goToCheckout(message, item)" @restart="chat.restartOrder(message.draftId)"
              @placed="(order) => chat.markPlaced(message.draftId, order)" />
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
      </template>
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
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.head-button {
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 999px;
  background: none;
  color: #fff;
  font-size: var(--step--1);
  padding: 2px 10px;
  white-space: nowrap; /* "Past chats" on one line */
  cursor: pointer;
}
.head-button:disabled {
  opacity: 0.6;
  cursor: default;
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

/* Answers to the stylist's follow-up questions */
.choices { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.choice {
  padding: 6px 12px;
  border: 1px solid var(--sindoor);
  border-radius: 999px;
  background: #fff;
  color: var(--sindoor-deep);
  font: inherit;
  font-size: var(--step--1);
  cursor: pointer;
}
.choice:hover:not(:disabled) { background: var(--sindoor-wash); }
.choice:disabled { cursor: default; opacity: 0.45; }
.choice.picked { opacity: 1; background: var(--sindoor); color: #fff; }
.choice-note { font-weight: 600; }

.bubble { max-width: 88%; }
.bubble.wide { max-width: 100%; } /* room for the order form */
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
/* Past chats */
.history-error {
  margin: 0;
  padding: 8px 16px;
  font-size: var(--step--1);
  color: var(--sindoor-deep);
  background: var(--jamdani);
}
.past-chat {
  display: flex;
  align-items: stretch;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--jamdani);
}
.past-chat:hover { border-color: var(--sindoor); }
.past-open {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border: 0;
  background: none;
  color: var(--kohl);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.past-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.past-date { font-size: var(--step--1); color: var(--muted); }
.past-delete {
  border: 0;
  border-left: 1px solid var(--line);
  background: none;
  color: var(--muted);
  font: inherit;
  font-size: var(--step--1);
  padding: 0 12px;
  cursor: pointer;
}
.past-delete:hover { color: var(--sindoor-deep); }

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
