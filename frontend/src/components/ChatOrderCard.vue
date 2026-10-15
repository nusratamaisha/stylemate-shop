<script setup>
// The finished order at the end of the stylist's follow-up questions (stores/chat.js, utils/chatOrder.js).
// It shows what the customer chose with the shop's price, then either fills the bag and opens
// checkout, or, like a shop answering on Messenger, takes the delivery details right here.
// Either way the order goes through POST /api/orders, which checks and prices it again.
import { computed, reactive, ref, useId, watchEffect } from 'vue'
import { api } from '../api.js'
import CheckoutFields from './CheckoutFields.vue'
import { refreshProducts } from '../stores/shop.js'
import { chosenOptionIds } from '../utils/chatOrder.js'
import { formatTaka, readyDate } from '../utils/format.js'

const props = defineProps({
  draft: { type: Object, required: true }, // { order, size, colour, quantity, changes }
  inBag: { type: Boolean, default: false },
})
const emit = defineEmits(['checkout', 'restart'])

const product = computed(() => props.draft.order.product)
const optionIds = computed(() => chosenOptionIds(props.draft))

// With changes, the price and the ready date come from Flask (pricing.py), never from the browser.
const quote = ref(null)
const quoteError = ref('')
watchEffect(async () => {
  if (!optionIds.value.length) return (quote.value = null)
  try {
    quote.value = await api('/price-quote', { method: 'POST', body: { product_code: product.value.code, option_ids: optionIds.value } })
  } catch (err) {
    quoteError.value = err.message
  }
})
const unitPrice = computed(() => quote.value?.total_bdt ?? product.value.price_bdt)
const pricing = computed(() => optionIds.value.length && !quote.value) // waiting for the quote

// The line as the bag and the order expect it
const item = computed(() => ({
  product_code: product.value.code,
  name: product.value.name,
  image_url: product.value.image_url,
  colours: product.value.colours,
  size: props.draft.size,
  colour: props.draft.colour,
  quantity: props.draft.quantity,
  option_ids: optionIds.value,
  custom_details: quote.value?.details || '',
  notes: '',
  unit_price_bdt: unitPrice.value, // shown in the bag; checkout recalculates it
}))

const idPrefix = `chat-order-${useId()}` // one chat can hold several orders, so field ids must differ
const step = ref('summary') // 'summary' -> 'details' -> 'done'
const customer = reactive({ name: '', phone: '', address: '', delivery_area: '' })
const payment = reactive({ method: '', transaction_id: '' })
const placing = ref(false)
const error = ref('')
const confirmation = ref(null)

async function confirmOrder() {
  error.value = ''
  placing.value = true
  try {
    const { product_code, size, colour, quantity, option_ids } = item.value
    confirmation.value = await api('/orders', {
      method: 'POST',
      body: {
        source: 'chat', // the owner sees a "Chat" badge on it in the Orders tab
        customer,
        payment,
        items: [{ product_code, size, colour, quantity, option_ids }], // no price: the server works it out
      },
    })
    step.value = 'done'
    refreshProducts() // the order lowered the stock
  } catch (err) {
    error.value = err.message
  } finally {
    placing.value = false
  }
}
</script>

<template>
  <div class="order">
    <p class="order-summary">
      <strong>{{ product.name }}</strong><br />
      Size {{ draft.size }}, {{ draft.colour }}<span v-if="draft.quantity > 1">, {{ draft.quantity }} pieces</span><br />
      <span v-if="quote?.details" class="changes">{{ quote.details }}<br /></span>
      <strong>{{ pricing ? 'Working out the price…' : formatTaka(unitPrice * draft.quantity) }}</strong>
      <span v-if="quote?.ready_in_days" class="muted"> · made to order, ready around {{ readyDate(quote.ready_in_days) }}</span>
    </p>
    <p v-if="quoteError" class="message error" role="alert">{{ quoteError }}</p>

    <div v-if="step === 'summary'" class="actions">
      <button type="button" class="button small" :disabled="pricing" @click="emit('checkout', item)">
        {{ inBag ? 'Back to checkout' : 'Go to checkout' }}
      </button>
      <button type="button" class="text-button small" :disabled="pricing" @click="step = 'details'">Or confirm here in the chat</button>
      <button type="button" class="text-button small" @click="emit('restart')">Change my answers</button>
    </div>

    <form v-else-if="step === 'details'" class="details" @submit.prevent="confirmOrder">
      <p class="order-note">A few details to send your order:</p>
      <CheckoutFields :customer="customer" :payment="payment" :subtotal="unitPrice * draft.quantity" :id-prefix="idPrefix" />
      <p v-if="error" class="message error" role="alert">{{ error }}</p>
      <div class="actions">
        <button type="submit" class="button small" :disabled="placing">
          {{ placing ? 'Confirming…' : 'Confirm order' }}
        </button>
        <button type="button" class="text-button small" :disabled="placing" @click="step = 'summary'">Back</button>
      </div>
    </form>

    <div v-else class="done" role="status">
      <p>
        <strong>Order confirmed, thank you {{ customer.name }}!</strong><br />
        <template v-if="confirmation.customer_order_number">Your order {{ confirmation.customer_order_number }} (ref #{{ confirmation.order_id }})</template>
        <template v-else>Order ref #{{ confirmation.order_id }}</template>
        · total {{ formatTaka(confirmation.total_bdt) }}, including {{ formatTaka(confirmation.shipping_bdt) }} delivery.
      </p>
      <p class="order-note">
        <template v-if="confirmation.payment_status === 'to_check'">
          We'll check your {{ confirmation.payment_label }} payment ({{ confirmation.payment_reference }}) and then send it.
        </template>
        <template v-else>You pay cash on delivery.</template>
        The shop will contact you on {{ customer.phone }}.
      </p>
    </div>
  </div>
</template>

<style scoped>
.order {
  margin-top: 10px;
  padding: 12px;
  border-radius: var(--radius);
  background: #fff;
  border: 1px solid var(--line);
}
.order-summary { margin: 0 0 10px; font-size: var(--step--1); line-height: 1.5; }
.changes { color: var(--muted); }
.order-note { margin: 8px 0; font-size: var(--step--1); color: var(--muted); }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-top: 8px; }
.details { margin-top: 4px; font-size: var(--step--1); }
.done p { margin: 0 0 6px; font-size: var(--step--1); }
.done strong { color: var(--sindoor-deep); }
</style>
