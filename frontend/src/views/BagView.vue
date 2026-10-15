<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api.js'
import CheckoutFields from '../components/CheckoutFields.vue'
import ProductImage from '../components/ProductImage.vue'
import { useAccount } from '../stores/account.js'
import { useBag } from '../stores/bag.js'
import { refreshProducts } from '../stores/shop.js'
import { formatDate, formatTaka } from '../utils/format.js'

const bag = useBag()
const account = useAccount()
const customer = reactive({ name: '', phone: '', address: '', delivery_area: '' })
// Delivery, payment and contact fields, the total and the account prefill live in CheckoutFields
const payment = reactive({ method: '', transaction_id: '' })

const placing = ref(false)
const error = ref('')
const confirmation = ref(null)

async function placeOrder() {
  error.value = ''
  placing.value = true
  try {
    confirmation.value = await api('/orders', {
      method: 'POST',
      body: {
        customer,
        payment, // a transaction ID left over from a wallet choice is ignored for cash
        // Prices are not sent: the server works them out again.
        items: bag.items.value.map(({ product_code, size, colour, quantity, option_ids, notes, measurements, reference_image }) =>
          ({ product_code, size, colour, quantity, option_ids, notes, measurements, reference_image })),
      },
    })
    bag.clear()
    refreshProducts() // the order lowered the stock, so the shop pages should show the new numbers
  } catch (err) {
    error.value = err.message
  } finally {
    placing.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1 class="title">Your bag</h1>

    <section v-if="confirmation" class="confirmation" role="status">
      <h2>Thank you, {{ customer.name }}</h2>
      <p>
        <template v-if="confirmation.customer_order_number">Your order {{ confirmation.customer_order_number }} (ref #{{ confirmation.order_id }})</template>
        <template v-else>Order ref #{{ confirmation.order_id }}</template>
        is placed. Total {{ formatTaka(confirmation.total_bdt) }}
        (including {{ formatTaka(confirmation.shipping_bdt) }} delivery).
        <template v-if="confirmation.payment_status === 'to_check'">
          We will check your {{ confirmation.payment_label }} payment ({{ confirmation.payment_reference }}) and confirm your order.
        </template>
        <template v-else>You pay cash on delivery.</template>
      </p>
      <ul>
        <li v-for="item in confirmation.items" :key="item.id">
          {{ item.product_name }} ({{ item.size }}, {{ item.colour }}) × {{ item.quantity }}
          <span v-if="item.is_custom"> made to order, ready around {{ formatDate(item.ready_by) }}</span>
        </li>
      </ul>
      <RouterLink to="/shop" class="button secondary">Keep shopping</RouterLink>
      <RouterLink v-if="account.state.customer" to="/account" class="text-link">See your orders</RouterLink>
    </section>

    <div v-else-if="!bag.items.value.length" class="empty">
      <p>Your bag is empty.</p>
      <RouterLink to="/shop" class="button">Browse the collection</RouterLink>
    </div>

    <div v-else class="layout">
      <ul class="lines">
        <li v-for="item in bag.items.value" :key="item.key" class="line">
          <ProductImage :product="{ name: item.name, image_url: item.image_url, colours: item.colours }" :colour="item.colour" class="thumb" />
          <div class="line-info">
            <RouterLink :to="`/products/${item.product_code}`" class="line-name">{{ item.name }}</RouterLink>
            <p class="small muted">{{ item.measurements ? item.size : `Size ${item.size}` }}, {{ item.colour }}</p>
            <p v-if="item.custom_details" class="small"><span class="tag custom">Made to order</span> {{ item.custom_details }}</p>
            <p v-if="item.notes" class="small muted">Notes: {{ item.notes }}</p>
            <p v-if="item.reference_image" class="small muted">Reference picture attached for the tailor</p>
            <div class="qty">
              <button type="button" class="pill" aria-label="One fewer" @click="bag.setQuantity(item.key, item.quantity - 1)">−</button>
              <span aria-live="polite">{{ item.quantity }}</span>
              <button type="button" class="pill" aria-label="One more" @click="bag.setQuantity(item.key, item.quantity + 1)">+</button>
              <button type="button" class="text-button small" @click="bag.remove(item.key)">Remove</button>
            </div>
          </div>
          <p class="line-price">{{ formatTaka(item.unit_price_bdt * item.quantity) }}</p>
        </li>
      </ul>

      <form class="checkout" @submit.prevent="placeOrder">
        <h2 class="checkout-title">Checkout</h2>
        <p v-if="account.state.loaded && !account.state.customer" class="small">
          <RouterLink to="/account">Log in</RouterLink> first to save this order to your account. You can also order as a guest.
        </p>
        <p v-else-if="account.state.customer" class="small muted">This order will be saved to your account.</p>
        <CheckoutFields :customer="customer" :payment="payment" :subtotal="bag.total.value" id-prefix="checkout" />

        <p v-if="error" class="message error">{{ error }}</p>
        <button type="submit" class="button full" :disabled="placing">{{ placing ? 'Placing your order…' : 'Place order' }}</button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.title {
  padding-top: 40px;
}
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
  gap: 40px;
  align-items: start;
}
.lines {
  list-style: none;
  margin: 0;
  padding: 0;
}
.line {
  display: grid;
  grid-template-columns: 90px 1fr auto;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid var(--line);
}
.line:first-child {
  border-top: 1px solid var(--line);
}
.line p {
  margin: 2px 0;
}
.line-name {
  font-family: var(--font-display);
  font-size: 1.125rem;
  color: var(--kohl);
}
.qty {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.qty .pill {
  min-height: 32px;
  width: 32px;
  padding: 0;
}
.line-price {
  font-weight: 600;
}
.checkout {
  padding: 24px;
  border-radius: 10px;
  background: var(--jamdani);
  position: sticky;
  top: 92px;
}
.checkout-title {
  font-size: var(--step-2);
}
.full {
  width: 100%;
}
.text-link {
  margin-left: 16px;
}
.confirmation {
  padding: 28px;
  border-radius: 10px;
  background: #e9f3ee;
}
.empty {
  padding: 24px 0;
}
@media (max-width: 800px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .checkout {
    position: static;
  }
  .line {
    grid-template-columns: 70px 1fr;
  }
  .line-price {
    grid-column: 2;
  }
}
</style>
