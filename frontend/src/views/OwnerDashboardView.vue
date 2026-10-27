<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import ProductImage from '../components/ProductImage.vue'
import { formatDate, formatTaka } from '../utils/format.js'

const router = useRouter()
const owner = ref(null)
const tab = ref('sales')

const business = ref(null) // what to restock, what not to, best sellers, this month against last
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
// The line's status and the ones it may move to: Flask decides (OrderItem.NEXT_STATUSES), so a
// shipped line offers nothing else, and a ready-made one skips "In production"
function statusOptions(item) {
  return Object.fromEntries([item.status, ...(item.next_statuses || [])].map((key) => [key, STATUS_LABELS[key]]))
}

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
  insights: async () => (business.value = await api('/owner/business')),
  sales: async () => (sales.value = await api('/owner/orders')),
  orders: async () => (orders.value = await api(`/owner/custom-orders${orderFilter.value ? `?status=${orderFilter.value}` : ''}`)),
  products: async () => (products.value = await api('/owner/products')),
  messages: async () => (messages.value = await api('/owner/messages')),
}

// The shop's plan use this month (services/plans.py); only meters at 80% or more are shown
const usage = ref(null)
const KIND_LABELS = { chat: 'AI chat questions', preview: 'picture previews' }
const warnings = computed(() => (usage.value?.meters || []).filter((meter) => meter.warn))
const left = (meter) => Math.max(0, meter.limit - meter.used)
const number = (value) => value.toLocaleString('en-IN')

// This month against last month, e.g. "↑ 25%"; nothing to compare with when last month was 0
function change(now, before) {
  if (!before) return ''
  const percent = Math.round((100 * (now - before)) / before)
  return percent === 0 ? 'same as last month' : `${percent > 0 ? '↑' : '↓'} ${Math.abs(percent)}% on last month`
}
// Each Insights card shows its first few items; "Show all" opens the rest
const PREVIEW = 4
const expanded = ref({ restock: false, slow: false, made_to_measure: false })
const shown = (key) => (expanded.value[key] ? business.value[key] : business.value[key].slice(0, PREVIEW))
const toggle = (key) => (expanded.value[key] = !expanded.value[key])
const TREND_ROWS = [
  ['sales_bdt', 'sales', true],
  ['orders', 'orders', false],
  ['pieces', 'pieces sold', false],
  ['questions', 'chat questions', false],
]

onMounted(() => load(async () => {
  owner.value = await api('/owner/me')
  api('/owner/usage').then((data) => (usage.value = data)).catch(() => {}) // a warning is a bonus, never an error
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

// An order line as the photo component expects a product; with no photo it shows the colour instead
const pieceOf = (item) => ({ name: item.product_name, image_url: item.product_image_url, colours: [item.colour] })

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

    <!-- Always visible: what is left of this month's plan (GET /api/owner/usage) -->
    <section v-if="usage?.meters.length" class="usage" aria-label="This month's plan use">
      <p class="usage-plan"><strong>{{ usage.plan }} plan</strong> <span class="muted">· this month</span></p>
      <div v-for="meter in usage.meters" :key="meter.kind" class="meter">
        <p class="meter-text">
          <span class="meter-name">{{ KIND_LABELS[meter.kind] }}</span>
          <span><strong>{{ number(left(meter)) }} left</strong> <span class="muted">of {{ number(meter.limit) }}</span></span>
        </p>
        <div class="bar" role="progressbar" :aria-valuenow="meter.used" aria-valuemin="0" :aria-valuemax="meter.limit"
          :aria-label="`${KIND_LABELS[meter.kind]} used`">
          <span :class="{ warn: meter.warn, over: meter.over }" :style="{ width: `${Math.min(100, (meter.used / meter.limit) * 100)}%` }"></span>
        </div>
      </div>
    </section>

    <div v-for="meter in warnings" :key="meter.kind" class="plan-warning" :class="{ over: meter.over }" role="status">
      <strong>{{ usage.plan }} plan:</strong>
      {{ meter.used.toLocaleString('en-IN') }} of {{ meter.limit.toLocaleString('en-IN') }} {{ KIND_LABELS[meter.kind] }} used this month.
      <template v-if="meter.over">
        You’ve reached the limit. Your shop keeps going for 10% more, then customers are asked to message you instead.
        Contact StyleMate to move to a bigger plan.
      </template>
      <template v-else>You’re close to the limit; it starts again on the 1st.</template>
    </div>

    <div class="tabs" role="tablist">
      <button v-for="[key, label] in [['sales', 'Orders'], ['insights', 'Insights'], ['orders', 'Custom orders'], ['products', 'Products'], ['messages', 'Messages']]"
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
                  <div class="piece">
                    <ProductImage :product="pieceOf(item)" :colour="item.colour" class="piece-photo" />
                    <div>
                      {{ item.product_name }}<br />
                      <span class="small muted">{{ item.is_custom && item.size === 'Made to measure' ? item.size : `Size ${item.size}` }}, {{ item.colour }}</span>
                      <span v-if="item.custom_details" class="small"><br />{{ item.custom_details }}</span>
                    </div>
                  </div>
                </td>
                <td>
                  <span class="tag" :class="item.is_custom ? 'custom' : 'out'">{{ item.is_custom ? 'Made to order' : 'Ready-made' }}</span>
                </td>
                <td>{{ item.quantity }}</td>
                <td>{{ formatTaka(item.unit_price_bdt * item.quantity) }}</td>
                <td>
                  <label class="visually-hidden" :for="`line-status-${item.id}`">Status</label>
                  <select :id="`line-status-${item.id}`" :value="item.status" :disabled="!item.next_statuses?.length" @change="setStatus(item, $event.target.value)">
                  <option v-for="(label, key) in statusOptions(item)" :key="key" :value="key">{{ label }}</option>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <!-- How the business is going (services/insights.business_insights) -->
    <section v-if="tab === 'insights' && business" class="panel insights">
      <!-- 1. The month at a glance -->
      <div class="insight-block">
        <h2 class="section-title">{{ business.trend.this_month_name }} so far</h2>
        <div class="stats four">
          <div v-for="[key, label, money] in TREND_ROWS" :key="key" class="stat">
            <span class="stat-value">{{ money ? formatTaka(business.trend.this_month[key]) : business.trend.this_month[key] }}</span>
            <span>{{ label }}</span>
            <span class="small trend">
              {{ change(business.trend.this_month[key], business.trend.last_month[key]) ||
                `${business.trend.last_month_name}: ${money ? formatTaka(business.trend.last_month[key]) : business.trend.last_month[key]}` }}
            </span>
          </div>
        </div>
      </div>

      <!-- 2. Stock decisions: three cards side by side, each with the same header and list -->
      <div class="insight-block">
        <h2 class="section-title">Stock to act on</h2>
        <div class="cards three">
          <article class="card">
            <header class="card-head">
              <h3>Restock now</h3>
              <span class="tag" :class="business.restock.length ? 'urgent' : 'out'">{{ business.restock.length }}</span>
            </header>
            <p class="card-note">Selling fast, with two weeks of stock or less at the last {{ business.recent_days }} days’ pace.</p>
            <ul v-if="business.restock.length" class="insight-list">
              <li v-for="item in shown('restock')" :key="item.code">
                <ProductImage :product="item" class="piece-photo" />
                <div>
                  <strong>{{ item.name }}</strong>
                  <span class="small muted">{{ item.sold_recently }} sold lately · {{ item.stock }} left</span>
                </div>
                <span class="tag" :class="item.days_left <= 3 ? 'urgent' : 'warn'">
                  {{ item.stock === 0 ? 'Sold out' : `${item.days_left} ${item.days_left === 1 ? 'day' : 'days'}` }}
                </span>
              </li>
            </ul>
            <p v-else class="card-empty">Nothing is running low.</p>
            <button v-if="business.restock.length > PREVIEW" type="button" class="text-button small" @click="toggle('restock')">
              {{ expanded.restock ? 'Show fewer' : `Show all ${business.restock.length}` }}
            </button>
          </article>

          <article class="card">
            <header class="card-head">
              <h3>Think before restocking</h3>
              <span class="tag" :class="business.slow.length ? 'warn' : 'out'">{{ business.slow.length }}</span>
            </header>
            <p class="card-note">
              In stock, no ready-made sale in {{ business.recent_days }} days.
              <template v-if="business.days_of_orders < business.recent_days">
                Early days: your first order was {{ business.days_of_orders }} {{ business.days_of_orders === 1 ? 'day' : 'days' }} ago.
              </template>
            </p>
            <ul v-if="business.slow.length" class="insight-list">
              <li v-for="item in shown('slow')" :key="item.code">
                <ProductImage :product="item" class="piece-photo" />
                <div>
                  <strong>{{ item.name }}</strong>
                  <span class="small muted">
                    {{ item.last_sold ? `Last sold ${formatDate(item.last_sold)}` : 'Never sold' }}<template v-if="item.rating"> · ★ {{ item.rating }}</template>
                  </span>
                </div>
                <span class="small muted nowrap">{{ item.stock }} in stock</span>
              </li>
            </ul>
            <p v-else class="card-empty">Everything in stock has sold lately.</p>
            <button v-if="business.slow.length > PREVIEW" type="button" class="text-button small" @click="toggle('slow')">
              {{ expanded.slow ? 'Show fewer' : `Show all ${business.slow.length}` }}
            </button>
          </article>

          <article class="card">
            <header class="card-head">
              <h3>Often made to measure</h3>
              <span class="tag" :class="business.made_to_measure.length ? 'warn' : 'out'">{{ business.made_to_measure.length }}</span>
            </header>
            <p class="card-note">Half or more of these orders were made to measure, so the standard sizes may not fit.</p>
            <ul v-if="business.made_to_measure.length" class="insight-list">
              <li v-for="item in shown('made_to_measure')" :key="item.code">
                <ProductImage :product="item" class="piece-photo" />
                <div>
                  <strong>{{ item.name }}</strong>
                  <span class="small muted">{{ item.made_to_measure }} of {{ item.orders }} orders · sizes {{ item.sizes.join(', ') }}</span>
                </div>
                <span class="tag warn">{{ item.share }}%</span>
              </li>
            </ul>
            <p v-else class="card-empty">Your standard sizes fit most customers.</p>
            <button v-if="business.made_to_measure.length > PREVIEW" type="button" class="text-button small" @click="toggle('made_to_measure')">
              {{ expanded.made_to_measure ? 'Show fewer' : `Show all ${business.made_to_measure.length}` }}
            </button>
          </article>
        </div>
      </div>

      <!-- 3. Best sellers -->
      <div class="insight-block">
        <h2 class="section-title">Best sellers</h2>
        <article class="card">
          <p class="card-note">All time, with the size and colour customers choose most, so you restock the right ones.</p>
          <div v-if="business.best_sellers.length" class="table-wrap">
            <table class="best-table">
              <thead><tr><th>Piece</th><th class="num">Sold</th><th class="num">Sales</th><th>Most popular</th><th>Rating</th><th class="num">Stock</th></tr></thead>
              <tbody>
                <tr v-for="item in business.best_sellers" :key="item.code">
                  <td><div class="piece"><ProductImage :product="item" class="piece-photo" /><strong>{{ item.name }}</strong></div></td>
                  <td class="num">{{ item.sold }}</td>
                  <td class="num">{{ formatTaka(item.revenue_bdt) }}</td>
                  <td>{{ item.top_size }}, {{ item.top_colour }}</td>
                  <td>{{ item.rating ? `★ ${item.rating} (${item.reviews})` : '–' }}</td>
                  <td class="num">{{ item.stock }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="card-empty">No orders yet.</p>
        </article>
      </div>

      <!-- 4. From the stylist chat: summaries only. The conversations themselves are not shown. -->
      <div class="insight-block">
        <h2 class="section-title">From the stylist chat</h2>
        <article class="card chat-card">
          <div class="chat-numbers">
            <div>
              <span class="stat-value">{{ business.chat.answer_rate === null ? '–' : `${business.chat.answer_rate}%` }}</span>
              <span class="small">of {{ business.chat.total_questions }} questions answered from your catalogue</span>
              <span class="small muted">{{ business.chat.voice_count }} asked by voice</span>
            </div>
            <div>
              <span class="stat-value">{{ business.chat.chat_orders }} of {{ business.chat.order_count }}</span>
              <span class="small">orders confirmed in the chat</span>
            </div>
          </div>
          <div class="chat-topics">
            <h3>What customers want that you don’t sell</h3>
            <p class="card-note">Questions your catalogue couldn’t answer, by topic. A big topic is worth stocking, or describing better if you sell it.</p>
            <ul v-if="business.chat.missing.length" class="topic-list">
              <li v-for="item in business.chat.missing" :key="item.topic">
                <div class="topic-head">
                  <strong>{{ item.topic }}</strong>
                  <span class="tag" :class="item.topic === 'Other' ? 'out' : 'warn'">{{ item.count }}×</span>
                </div>
                <span v-if="item.examples.length" class="small muted">{{ item.examples.map((example) => `“${example}”`).join(' · ') }}</span>
              </li>
            </ul>
            <p v-else class="card-empty">Nothing yet. Every question so far matched your catalogue.</p>
          </div>
        </article>
      </div>
    </section>

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
              <td>
                <div class="piece">
                  <ProductImage :product="pieceOf(item)" :colour="item.colour" class="piece-photo" />
                  <div>{{ item.product_name }}<br /><span class="small muted">{{ item.size }}, {{ item.colour }} × {{ item.quantity }}</span></div>
                </div>
              </td>
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
                <select :id="`status-${item.id}`" :value="item.status" :disabled="!item.next_statuses?.length" @change="setStatus(item, $event.target.value)">
                  <option v-for="(label, key) in statusOptions(item)" :key="key" :value="key">{{ label }}</option>
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
/* Insights: four blocks, each a heading over one card or a row of cards */
.insights {
  display: grid;
  gap: 36px;
}
.insight-block .section-title {
  margin: 0 0 12px;
}
.insights .stats {
  margin-bottom: 0;
}
.trend {
  margin-top: 4px;
  color: var(--muted);
}
.cards.three {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}
.card {
  display: grid;
  gap: 10px;
  align-content: start;
  min-width: 0;
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius-large);
  background: #fff;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.card h3 {
  margin: 0;
  font-family: var(--font-body);
  font-size: 1rem;
  font-weight: 600;
}
.card-note {
  margin: 0;
  max-width: none;
  font-size: var(--step--1);
  color: var(--muted);
}
.card-empty {
  margin: 0;
  padding: 14px 0 4px;
  color: var(--muted);
}
.card > .text-button {
  justify-self: start;
}
.insight-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.insight-list li {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid var(--line);
}
.insight-list li > div {
  display: grid;
  min-width: 0;
}
.insight-list strong {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.insight-list .piece-photo {
  width: 40px;
}
.nowrap {
  white-space: nowrap;
}
.tag.warn {
  background: #fbf2dc;
  color: #6b4a05;
}
.tag.urgent {
  background: #fbeceb;
  color: var(--danger);
}
.best-table td {
  vertical-align: middle;
}
.best-table strong {
  font-weight: 500;
}
.best-table .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  padding-right: 24px;
}
.chat-card {
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: 28px;
}
.chat-numbers {
  display: grid;
  gap: 16px;
  align-content: start;
}
.chat-numbers > div {
  display: grid;
  gap: 2px;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--jamdani);
}
.chat-topics {
  display: grid;
  gap: 8px;
  align-content: start;
}
.topic-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.topic-list li {
  display: grid;
  gap: 2px;
  padding: 10px 0;
  border-top: 1px solid var(--line);
}
.topic-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
@media (max-width: 1000px) {
  .cards.three {
    grid-template-columns: minmax(0, 1fr);
  }
  .chat-card {
    grid-template-columns: minmax(0, 1fr);
  }
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
.piece {
  display: flex;
  align-items: center;
  gap: 12px;
}
.piece-photo {
  flex: none;
  width: 48px; /* the photo keeps its 3:4 shape, so it is 64px tall */
  border-radius: 6px;
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
.usage {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 32px;
  margin: 0 0 16px;
  padding: 14px 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #fff;
}
.usage-plan {
  margin: 0;
}
.meter {
  flex: 1;
  min-width: 220px;
}
.meter-text {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 6px;
  font-size: var(--step--1);
}
.meter-name::first-letter {
  text-transform: uppercase; /* "Picture previews" here, "picture previews" mid-sentence in the warning */
}
.bar {
  height: 6px;
  border-radius: 999px;
  background: var(--jamdani);
  overflow: hidden;
}
.bar span {
  display: block;
  height: 100%;
  background: var(--ok);
}
.bar span.warn {
  background: var(--haldi);
}
.bar span.over {
  background: var(--danger);
}
.plan-warning {
  margin: 0 0 16px;
  padding: 12px 16px;
  border-radius: var(--radius);
  background: #fbf2dc;
  color: #6b4a05;
}
.plan-warning.over {
  background: #f9e3e4;
  color: var(--danger);
}
</style>
