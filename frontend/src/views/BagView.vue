<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../api.js'
import ProductImage from '../components/ProductImage.vue'
import { useAccount } from '../stores/account.js'
import { useBag } from '../stores/bag.js'
import { refreshProducts, useShop } from '../stores/shop.js'
import { formatDate, formatTaka } from '../utils/format.js'

const bag = useBag()
const shop = useShop()
const account = useAccount()
const customer = reactive({ name: '', phone: '', address: '', delivery_area: '' })

// A logged-in customer doesn't retype what their account already knows.
watch(() => account.state.customer, (loggedIn) => {
  if (!loggedIn) return
  customer.name ||= loggedIn.name
  customer.phone ||= loggedIn.phone
}, { immediate: true })

// Shown so the customer sees the total before ordering. The server works the charge out again.
const shippingOptions = computed(() => shop.info?.shipping || [])
const shipping = computed(() => shippingOptions.value.find((option) => option.area === customer.delivery_area) || null)
const total = computed(() => bag.total.value + (shipping.value?.charge_bdt || 0))

// Cash on delivery, or the customer sends money to the shop's wallet and types the transaction ID.
// No money moves through this site; the owner checks the ID and marks the order as paid.
const payment = reactive({ method: '', transaction_id: '' })
const paymentOptions = computed(() => shop.info?.payment || [])
const wallet = computed(() => paymentOptions.value.find((option) => option.method === payment.method && option.number) || null)
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
        payment: { method: payment.method, transaction_id: wallet.value ? payment.transaction_id : '' },
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
        <fieldset class="delivery">
          <legend>Deliver to</legend>
          <label v-for="option in shippingOptions" :key="option.area" class="delivery-option">
            <input v-model="customer.delivery_area" type="radio" name="delivery-area" :value="option.area" required />
            <span>{{ option.label }}</span>
            <span class="delivery-charge">{{ formatTaka(option.charge_bdt) }}</span>
          </label>
        </fieldset>

        <p class="sum"><span>Subtotal</span><span>{{ formatTaka(bag.total.value) }}</span></p>
        <p class="sum">
          <span>Delivery</span>
          <span>{{ shipping ? formatTaka(shipping.charge_bdt) : 'Choose an area' }}</span>
        </p>
        <p class="total"><span>Total</span><span>{{ formatTaka(total) }}</span></p>

        <fieldset class="delivery pay">
          <legend>Pay by</legend>
          <label v-for="option in paymentOptions" :key="option.method" class="delivery-option">
            <input v-model="payment.method" type="radio" name="payment-method" :value="option.method" required />
            <span>{{ option.label }}</span>
          </label>
        </fieldset>
        <div v-if="wallet" class="wallet">
          <ol class="small">
            <li>In your {{ wallet.label }} app, choose Send Money.</li>
            <li>Send <strong>{{ formatTaka(total) }}</strong> to <strong>{{ wallet.number }}</strong>.</li>
            <li>Type the transaction ID (TrxID) from the confirmation message below.</li>
          </ol>
          <div class="field">
            <label for="transaction-id">{{ wallet.label }} transaction ID</label>
            <input id="transaction-id" v-model="payment.transaction_id" autocomplete="off" autocapitalize="characters"
              minlength="6" maxlength="20" required aria-describedby="transaction-help" />
            <p id="transaction-help" class="small muted">We check it before sending your order.</p>
          </div>
        </div>

        <div class="field">
          <label for="name">Full name</label>
          <input id="name" v-model="customer.name" autocomplete="name" required />
        </div>
        <div class="field">
          <label for="phone">Phone number</label>
          <input id="phone" v-model="customer.phone" type="tel" autocomplete="tel" required />
        </div>
        <div class="field">
          <label for="address">Delivery address</label>
          <textarea id="address" v-model="customer.address" rows="3" autocomplete="street-address" required></textarea>
        </div>

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
.delivery {
  border: 0;
  padding: 0;
  margin: 0 0 16px;
}
.delivery legend {
  font-weight: 600;
  margin-bottom: 8px;
  padding: 0;
}
.delivery-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #fff;
  font-weight: 400;
  cursor: pointer;
}
.delivery-option input {
  width: 18px;
  height: 18px;
  padding: 0;
}
.delivery-charge {
  margin-left: auto;
  font-weight: 600;
}
.wallet {
  padding: 12px;
  margin-bottom: 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #fff;
}
.wallet ol {
  margin: 0 0 12px;
  padding-left: 20px;
}
.pay {
  margin-top: 16px;
}
.sum {
  display: flex;
  justify-content: space-between;
  margin: 0 0 4px;
}
.total {
  padding-top: 8px;
  border-top: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  font-size: var(--step-1);
  font-weight: 600;
  margin: 0 0 4px;
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
