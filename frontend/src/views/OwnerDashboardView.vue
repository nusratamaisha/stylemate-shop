<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import { formatDate, formatTaka } from '../utils/format.js'
import { plainText } from '../utils/markdown.js'

const router = useRouter()
const owner = ref(null)
const tab = ref('sales')

const insights = ref(null)
const orders = ref([])
const sales = ref(null) // { summary, orders }: every order, ready-made and made to order
const orderFilter = ref('')
const products = ref([])
const messages = ref([])
const error = ref('')

const upload = ref(null)
const uploading = ref(false)
const uploadResult = ref(null)
const uploadError = ref('')
const syncing = ref(false)
const syncMessage = ref('')

const STATUS_LABELS = { new: 'New', in_production: 'In production', shipped: 'Shipped' }
const AREA_LABELS = { inside_dhaka: 'Inside Dhaka', outside_dhaka: 'Outside Dhaka' }
const PAYMENT_LABELS = { unpaid: 'Not paid yet', to_check: 'Check this payment', paid: 'Paid' }

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
  sales: async () => (sales.value = await api('/owner/orders')),
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
    if (tab.value === 'sales') sales.value.summary = (await api('/owner/orders')).summary // "to ship" changes
  })
}

// After looking in the wallet's history (or collecting the cash), the owner records the result.
async function setPayment(order, status) {
  await load(async () => {
    const updated = await api(`/owner/orders/${order.order_id}/payment`, { method: 'PATCH', body: { status } })
    order.payment_status = updated.payment_status
    sales.value.summary = (await api('/owner/orders')).summary // "payments to check" changes
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

async function syncStock() {
  syncing.value = true
  syncMessage.value = ''
  await load(async () => {
    syncMessage.value = (await api('/owner/products/sync', { method: 'POST' })).message
  })
  syncing.value = false
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
      <button v-for="[key, label] in [['sales', 'Orders'], ['questions', 'Customer questions'], ['orders', 'Custom orders'], ['products', 'Products'], ['messages', 'Messages']]"
        :key="key" role="tab" type="button" class="tab" :aria-selected="tab === key" @click="tab = key">
        {{ label }}
      </button>
    </div>

    <p v-if="error" class="message error">{{ error }}</p>

    <!-- Every order, with the sales numbers -->
    <section v-if="tab === 'sales' && sales" class="panel">
      <div class="stats four">
        <div class="stat"><span class="stat-value">{{ sales.summary.order_count }}</span><span>orders, {{ sales.summary.chat_orders }} confirmed in the chat</span></div>
        <div class="stat">
          <span class="stat-value">{{ formatTaka(sales.summary.sales_bdt) }}</span>
          <span>sales, plus {{ formatTaka(sales.summary.delivery_bdt) }} delivery collected</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ sales.summary.pieces_sold }}</span>
          <span>pieces sold, {{ sales.summary.custom_pieces }} made to order</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ sales.summary.to_ship }}</span>
          <span>lines still to ship, {{ sales.summary.payments_to_check }} {{ sales.summary.payments_to_check === 1 ? 'payment' : 'payments' }} to check</span>
        </div>
      </div>

      <div v-if="sales.summary.best_sellers.length" class="best">
        <h2 class="section-title">Best sellers</h2>
        <ol class="ranked">
          <li v-for="item in sales.summary.best_sellers" :key="item.name">
            <span>{{ item.name }}</span><span class="times">{{ item.quantity }} sold</span>
          </li>
        </ol>
      </div>

      <h2 class="section-title">All orders</h2>
      <p v-if="!sales.orders.length" class="muted">No orders yet.</p>
      <article v-for="order in sales.orders" :key="order.order_id" class="order-card">
        <header class="order-head">
          <strong>Order #{{ order.order_id }}</strong>
          <!-- Orders the customer confirmed in the stylist chat, not on the checkout page -->
          <span v-if="order.source === 'chat'" class="tag chat">Chat</span>
          <span class="muted small">{{ formatDate(order.ordered_at) }}</span>
          <span class="order-total">{{ formatTaka(order.total_bdt) }}</span>
        </header>
        <p class="small order-who">
          {{ order.customer_name }} · {{ order.phone }}<span v-if="order.has_account" class="tag custom">Has an account</span><br />
          <span class="muted">{{ order.address }} · {{ AREA_LABELS[order.delivery_area] || 'Area not given' }}
            ({{ formatTaka(order.shipping_bdt) }} delivery)</span>
        </p>
        <p class="small payment">
          <span>{{ order.payment_label }}<template v-if="order.payment_reference">, TrxID <strong>{{ order.payment_reference }}</strong></template></span>
          <span class="tag" :class="order.payment_status === 'paid' ? 'custom' : 'out'">{{ PAYMENT_LABELS[order.payment_status] }}</span>
          <button v-if="order.payment_status !== 'paid'" type="button" class="button secondary small" @click="setPayment(order, 'paid')">Mark as paid</button>
          <button v-else type="button" class="text-button small" @click="setPayment(order, order.payment_reference ? 'to_check' : 'unpaid')">Undo</button>
        </p>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Piece</th><th>Type</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-for="item in order.items" :key="item.id">
                <td>
                  {{ item.product_name }}<br />
                  <span class="small muted">{{ item.is_custom && item.size === 'Made to measure' ? item.size : `Size ${item.size}` }}, {{ item.colour }}</span>
                  <span v-if="item.custom_details" class="small"><br />{{ item.custom_details }}</span>
                </td>
                <td>
                  <span class="tag" :class="item.is_custom ? 'custom' : 'out'">{{ item.is_custom ? 'Made to order' : 'Ready-made' }}</span>
                </td>
                <td>{{ item.quantity }}</td>
                <td>{{ formatTaka(item.unit_price_bdt * item.quantity) }}</td>
                <td>
                  <label class="visually-hidden" :for="`line-status-${item.id}`">Status</label>
                  <select :id="`line-status-${item.id}`" :value="item.status" @change="setStatus(item, $event.target.value)">
                    <option v-for="(label, key) in STATUS_LABELS" :key="key" :value="key">{{ label }}</option>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

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
              <td>
                {{ item.custom_details }}<br /><span v-if="item.notes" class="small muted">{{ item.notes }}</span>
                <a v-if="item.has_reference_image" :href="`/api/owner/custom-orders/${item.id}/reference-picture`"
                  target="_blank" rel="noopener" class="picture-link small">
                  <img :src="`/api/owner/custom-orders/${item.id}/reference-picture`" alt="" />
                  Customer’s reference picture
                </a>
              </td>
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

      <div class="sync">
        <p class="small muted">
          Orders lower the stock here straight away. The stylist chat only knows the stock it was last sent,
          so send it today’s numbers after a busy day or when something sells out.
        </p>
        <button type="button" class="button secondary small" :disabled="syncing" @click="syncStock">
          {{ syncing ? 'Sending…' : 'Send today’s stock to the stylist' }}
        </button>
        <p v-if="syncMessage" class="message ok" role="status">{{ syncMessage }}</p>
      </div>

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
          <thead><tr><th>Sent</th><th>From</th><th>Reply to</th><th>Message</th><th>Photo</th></tr></thead>
          <tbody>
            <tr v-for="message in messages" :key="message.id">
              <td>{{ formatDate(message.sent_at) }}</td>
              <td>{{ message.name }}</td>
              <td>{{ message.contact }}</td>
              <td class="message-text">{{ message.message }}</td>
              <td>
                <a v-if="message.has_picture" :href="`/api/owner/messages/${message.id}/picture`" target="_blank" rel="noopener"
                  class="message-photo" :aria-label="`Open the photo from ${message.name}`">
                  <img :src="`/api/owner/messages/${message.id}/picture`" alt="" />
                </a>
                <span v-else class="muted">None</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">No messages yet.</p>
    </section>
  </div>
</template>

<style scoped>
.sync {
  margin: 20px 0;
}
.stats.four {
  grid-template-columns: repeat(4, 1fr);
}
.best {
  max-width: 520px;
  margin-bottom: 32px;
}
.order-card {
  padding: 18px 20px;
  margin-bottom: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius-large);
  background: #fff;
}
.order-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.tag.chat { background: var(--sindoor-wash); color: var(--sindoor-deep); }
.order-total {
  margin-left: auto;
  font-weight: 600;
  font-size: var(--step-1);
}
.order-who {
  margin: 6px 0 10px;
  max-width: none;
}
.order-who .tag {
  margin-left: 8px;
}
.payment {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 0 0 10px;
  max-width: none;
}
.message-photo img {
  display: block;
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: var(--radius);
  border: 1px solid var(--line);
}
@media (max-width: 800px) {
  .stats.four {
    grid-template-columns: repeat(2, 1fr);
  }
}
.picture-link {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.picture-link img {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: 6px;
}
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
