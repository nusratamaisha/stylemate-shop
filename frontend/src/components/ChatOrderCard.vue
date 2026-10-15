<script setup>
// A piece the customer agreed to order in the chat, already checked by Flask (services/chat.py, read_order).
// Like a shop answering on Messenger, the customer can finish the order right here: the card asks for
// delivery, payment and contact details and confirms it, without leaving the chat. "Go to checkout"
// still works as before. Either way the order goes through POST /api/orders, which prices it again.
import { reactive, ref, useId } from 'vue'
import { api } from '../api.js'
import CheckoutFields from './CheckoutFields.vue'
import { refreshProducts } from '../stores/shop.js'
import { formatTaka } from '../utils/format.js'

const props = defineProps({
  order: { type: Object, required: true }, // { product, size, colour, quantity, unit_price_bdt }
  inBag: { type: Boolean, default: false },
})
const emit = defineEmits(['checkout'])

const idPrefix = `chat-order-${useId()}` // one chat can hold several order cards, so field ids must differ

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
    const { product, size, colour, quantity } = props.order
    confirmation.value = await api('/orders', {
      method: 'POST',
      body: {
        source: 'chat', // the owner sees a "Chat" badge on it in the Orders tab
        customer,
        payment,
        items: [{ product_code: product.code, size, colour, quantity }], // no price: the server works it out
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
      <strong>{{ order.product.name }}</strong><br />
      Size {{ order.size }}, {{ order.colour }}<span v-if="order.quantity > 1">, {{ order.quantity }} pieces</span>
      · {{ formatTaka(order.unit_price_bdt * order.quantity) }}
    </p>

    <template v-if="step === 'summary'">
      <div class="actions">
        <button type="button" class="button small" @click="step = 'details'">Order here in the chat</button>
        <button type="button" class="text-button small" @click="emit('checkout')">
          {{ inBag ? 'Back to checkout' : 'Or go to checkout' }}
        </button>
      </div>
    </template>

    <form v-else-if="step === 'details'" class="details" @submit.prevent="confirmOrder">
      <p class="order-note">A few details to send your order:</p>
      <CheckoutFields :customer="customer" :payment="payment" :subtotal="order.unit_price_bdt * order.quantity"
        :id-prefix="idPrefix" />
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
.order-summary { margin: 0 0 10px; font-size: var(--step--1); line-height: 1.4; }
.order-note { margin: 8px 0; font-size: var(--step--1); color: var(--muted); }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 8px; }
.details { margin-top: 4px; font-size: var(--step--1); }
.done p { margin: 0 0 6px; font-size: var(--step--1); }
.done strong { color: var(--sindoor-deep); }
</style>
