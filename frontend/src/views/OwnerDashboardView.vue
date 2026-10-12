<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import { formatDate, formatTaka } from '../utils/format.js'
import { plainText } from '../utils/markdown.js'

const router = useRouter()
const owner = ref(null)
const tab = ref('questions')

const insights = ref(null)
const orders = ref([])
const orderFilter = ref('')
const products = ref([])
const messages = ref([])
const error = ref('')

const upload = ref(null)
const uploading = ref(false)
const uploadResult = ref(null)
const uploadError = ref('')

const STATUS_LABELS = { new: 'New', in_production: 'In production', shipped: 'Shipped' }

async function load(fn) {
  error.value = ''
  try {
    await fn()
  } catch (err) {
    if (err.status === 401) router.replace('/owner/login')
    else error.value = err.message
  }
}

const loaders = {
  questions: async () => (insights.value = await api('/owner/insights')),
  orders: async () => (orders.value = await api(`/owner/custom-orders${orderFilter.value ? `?status=${orderFilter.value}` : ''}`)),
  products: async () => (products.value = await api('/owner/products')),
  messages: async () => (messages.value = await api('/owner/messages')),
}

onMounted(() => load(async () => {
  owner.value = await api('/owner/me')
  await loaders[tab.value]()
}))
watch(tab, (name) => load(loaders[name]))
watch(orderFilter, () => load(loaders.orders))

async function setStatus(item, status) {
  await load(async () => {
    const updated = await api(`/owner/custom-orders/${item.id}`, { method: 'PATCH', body: { status } })
    Object.assign(item, updated)
  })
}

async function uploadCsv() {
  const file = upload.value?.files?.[0]
  uploadError.value = ''
  uploadResult.value = null
  if (!file) {
    uploadError.value = 'Choose a CSV file first.'
    return
  }
  const form = new FormData()
  form.append('file', file)
  uploading.value = true
  try {
    uploadResult.value = await api('/owner/products/upload', { method: 'POST', form })
    upload.value.value = ''
    await loaders.products()
  } catch (err) {
    uploadError.value = err.message
  } finally {
    uploading.value = false
  }
}

async function logOut() {
  await api('/owner/logout', { method: 'POST' }).catch(() => {})
  router.push('/owner/login')
}
</script>

<template>
  <div class="page dashboard">
    <div class="top">
      <div>
        <h1>{{ owner?.shop.name || 'Your shop' }}</h1>
        <p class="muted small">Logged in as {{ owner?.email }}</p>
      </div>
      <button type="button" class="button secondary small" @click="logOut">Log out</button>
    </div>

    <div class="tabs" role="tablist">
      <button v-for="[key, label] in [['questions', 'Customer questions'], ['orders', 'Custom orders'], ['products', 'Products'], ['messages', 'Messages']]"
        :key="key" role="tab" type="button" class="tab" :aria-selected="tab === key" @click="tab = key">
        {{ label }}
      </button>
    </div>

    <p v-if="error" class="message error">{{ error }}</p>

    <!-- Customer questions -->
    <section v-if="tab === 'questions' && insights" class="panel">
      <div class="stats">
        <div class="stat"><span class="stat-value">{{ insights.total_questions }}</span><span>questions asked</span></div>
        <div class="stat">
          <span class="stat-value">{{ insights.answer_rate === null ? 'None yet' : `${insights.answer_rate}%` }}</span>
          <span>answered from your catalogue</span>
        </div>
        <div class="stat"><span class="stat-value">{{ insights.voice_count }}</span><span>asked by voice</span></div>
      </div>

      <div class="columns">
        <div>
          <h2 class="section-title">Most asked</h2>
          <ol v-if="insights.top_questions.length" class="ranked">
            <li v-for="item in insights.top_questions" :key="item.question">
              <span>{{ item.question }}</span><span class="times">{{ item.count }}×</span>
            </li>
          </ol>
          <p v-else class="muted">No questions yet. They appear here as customers use the chat.</p>
        </div>
        <div>
          <h2 class="section-title">Couldn’t answer</h2>
          <p class="muted small">
            Your catalogue had no good match for these. They show what customers want that you don’t sell,
            or haven’t described yet.
          </p>
          <ol v-if="insights.unanswered_questions.length" class="ranked gaps">
            <li v-for="item in insights.unanswered_questions" :key="item.question">
              <span>{{ item.question }}</span><span class="times">{{ item.count }}×</span>
            </li>
          </ol>
          <p v-else class="muted">Nothing yet.</p>
        </div>
      </div>

      <h2 class="section-title">Recent conversations</h2>
      <div v-if="insights.recent.length" class="recent">
        <div v-for="turn in insights.recent" :key="turn.asked_at" class="turn">
          <p class="q">
            {{ turn.question }}
            <span v-if="turn.via_voice" class="tag custom">Voice</span>
            <span v-if="!turn.answered" class="tag out">Not in catalogue</span>
          </p>
          <p class="a small muted">{{ plainText(turn.answer) }}</p>
        </div>
      </div>
      <p v-else class="muted">No conversations yet.</p>
    </section>

    <!-- Custom orders -->
    <section v-if="tab === 'orders'" class="panel">
      <div class="pills filter">
        <button type="button" class="pill" :aria-pressed="!orderFilter" @click="orderFilter = ''">All</button>
        <button v-for="(label, key) in STATUS_LABELS" :key="key" type="button" class="pill"
          :aria-pressed="orderFilter === key" @click="orderFilter = key">{{ label }}</button>
      </div>
      <div v-if="orders.length" class="table-wrap">
        <table>
          <thead>
            <tr><th>Order</th><th>Customer</th><th>Piece</th><th>Changes</th><th>Price</th><th>Ready by</th><th>Status</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in orders" :key="item.id">
              <td>{{ item.order_id }}<br /><span class="small muted">{{ formatDate(item.ordered_at) }}</span></td>
              <td>{{ item.customer_name }}<br /><span class="small muted">{{ item.phone }}</span></td>
              <td>{{ item.product_name }}<br /><span class="small muted">{{ item.size }}, {{ item.colour }} × {{ item.quantity }}</span></td>
              <td>{{ item.custom_details }}<br /><span v-if="item.notes" class="small muted">{{ item.notes }}</span></td>
              <td>{{ formatTaka(item.unit_price_bdt * item.quantity) }}</td>
              <td>{{ formatDate(item.ready_by) }}</td>
              <td>
                <label class="visually-hidden" :for="`status-${item.id}`">Status</label>
                <select :id="`status-${item.id}`" :value="item.status" @change="setStatus(item, $event.target.value)">
                  <option v-for="(label, key) in STATUS_LABELS" :key="key" :value="key">{{ label }}</option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">No custom orders {{ orderFilter ? 'with this status' : 'yet' }}.</p>
    </section>

    <!-- Products -->
    <section v-if="tab === 'products'" class="panel">
      <form class="upload" @submit.prevent="uploadCsv">
        <h2 class="section-title">Update products from a CSV</h2>
        <p class="muted small">
          Use the same columns as <code>data/products_sample.csv</code>. Rows with an existing product_id update that
          product; new IDs add products. The file also goes to the stylist, so it learns the changes.
        </p>
        <div class="upload-row">
          <label class="visually-hidden" for="csv">CSV file</label>
          <input id="csv" ref="upload" type="file" accept=".csv,text/csv" />
          <button type="submit" class="button small" :disabled="uploading">{{ uploading ? 'Uploading…' : 'Upload' }}</button>
        </div>
        <p v-if="uploadError" class="message error">{{ uploadError }}</p>
        <div v-if="uploadResult" class="message" :class="uploadResult.assistant_status === 'failed' ? 'error' : 'ok'">
          {{ uploadResult.created }} added, {{ uploadResult.updated }} updated. {{ uploadResult.assistant_message }}
        </div>
      </form>

      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Customizable</th></tr></thead>
          <tbody>
            <tr v-for="product in products" :key="product.code">
              <td>{{ product.code }}</td>
              <td><RouterLink :to="`/products/${product.code}`">{{ product.name }}</RouterLink></td>
              <td>{{ product.category }}</td>
              <td>{{ formatTaka(product.price_bdt) }}</td>
              <td>{{ product.stock }}</td>
              <td>{{ product.customizable ? 'Yes' : 'No' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Messages from the Help page -->
    <section v-if="tab === 'messages'" class="panel">
      <p class="muted small">Messages customers sent from the Help page, newest first. Reply by phone or email.</p>
      <div v-if="messages.length" class="table-wrap">
        <table>
          <thead><tr><th>Sent</th><th>From</th><th>Reply to</th><th>Message</th></tr></thead>
          <tbody>
            <tr v-for="message in messages" :key="message.id">
              <td>{{ formatDate(message.sent_at) }}</td>
              <td>{{ message.name }}</td>
              <td>{{ message.contact }}</td>
              <td class="message-text">{{ message.message }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">No messages yet.</p>
    </section>
  </div>
</template>

<style scoped>
.message-text {
  white-space: pre-wrap;
  min-width: 260px;
}
.dashboard {
  padding-top: 32px;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.top h1 {
  font-size: var(--step-3);
  margin-bottom: 0;
}
.tabs {
  display: flex;
  gap: 4px;
  margin: 24px 0;
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
}
.tab {
  padding: 12px 16px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: none;
  color: var(--muted);
  font: 600 var(--step-0) / 1 var(--font-body);
  cursor: pointer;
  white-space: nowrap;
}
.tab[aria-selected='true'] {
  color: var(--sindoor);
  border-bottom-color: var(--sindoor);
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}
.stat {
  display: flex;
  flex-direction: column;
  padding: 18px 20px;
  border-radius: 10px;
  background: var(--jamdani);
}
.stat-value {
  font-family: var(--font-display);
  font-size: var(--step-3);
  line-height: 1.1;
}
.columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 40px;
  margin-bottom: 32px;
}
.section-title {
  font-size: var(--step-1);
  font-family: var(--font-body);
  font-weight: 600;
}
.ranked {
  margin: 0;
  padding-left: 1.4em;
}
.ranked li {
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.ranked li span:first-child {
  margin-right: 8px;
}
.times {
  float: right;
  color: var(--muted);
}
.gaps li::marker {
  color: var(--sindoor);
}
.recent {
  display: grid;
  gap: 4px;
}
.turn {
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.turn p {
  margin: 0;
  max-width: none;
}
.q {
  font-weight: 500;
}
.a {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.filter {
  margin-bottom: 16px;
}
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--step--1);
}
th,
td {
  text-align: left;
  padding: 10px 12px 10px 0;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
th {
  font-weight: 600;
}
td select {
  min-width: 140px;
  padding: 6px 8px;
}
.upload {
  margin-bottom: 32px;
}
.upload-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.upload-row input {
  width: auto;
  flex: 1;
  min-width: 220px;
}
@media (max-width: 760px) {
  .stats,
  .columns {
    grid-template-columns: 1fr;
  }
}
</style>
