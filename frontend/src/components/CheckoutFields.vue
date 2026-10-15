<script setup>
// The details every order needs: delivery area, payment, name, phone and address, with the total.
// Used by the checkout page and by the order form in the stylist chat, so both ask the same
// questions (DRY: pulled out of BagView when the chat became the second place to order).
// The parent owns `customer` and `payment` and sends them to POST /api/orders.
import { computed, watch } from 'vue'
import { useAccount } from '../stores/account.js'
import { useShop } from '../stores/shop.js'
import { formatTaka } from '../utils/format.js'
import { deviceDetails, fillIn } from '../utils/savedDetails.js'

const props = defineProps({
  customer: { type: Object, required: true }, // { name, phone, address, delivery_area }
  payment: { type: Object, required: true }, // { method, transaction_id }
  subtotal: { type: Number, required: true },
  idPrefix: { type: String, required: true }, // the chat and the bag page can be open at once, so ids must differ
})

// Ticked: save these details for next time (to the account, or for a guest in this browser)
const remember = defineModel('remember', { type: Boolean, default: true })

const shop = useShop()
const account = useAccount()

// A returning customer doesn't retype what the shop or this device already knows (utils/savedDetails.js)
watch(() => [account.state.loaded, account.state.customer], ([loaded, loggedIn]) => {
  if (loggedIn) fillIn(props.customer, props.payment, loggedIn)
  else if (loaded) fillIn(props.customer, props.payment, deviceDetails())
}, { immediate: true })

// Shown so the customer sees the total before ordering. The server works the charge out again.
const shippingOptions = computed(() => shop.info?.shipping || [])
const shipping = computed(() => shippingOptions.value.find((option) => option.area === props.customer.delivery_area) || null)
const total = computed(() => props.subtotal + (shipping.value?.charge_bdt || 0))

// Cash on delivery, or the customer sends money to the shop's wallet and types the transaction ID.
// No money moves through this site; the owner checks the ID and marks the order as paid.
const paymentOptions = computed(() => shop.info?.payment || [])
const wallet = computed(() => paymentOptions.value.find((option) => option.method === props.payment.method && option.number) || null)
const id = (name) => `${props.idPrefix}-${name}`
</script>

<template>
  <fieldset class="choices">
    <legend>Deliver to</legend>
    <label v-for="option in shippingOptions" :key="option.area" class="choice">
      <input v-model="customer.delivery_area" type="radio" :name="id('delivery-area')" :value="option.area" required />
      <span>{{ option.label }}</span>
      <span class="charge">{{ formatTaka(option.charge_bdt) }}</span>
    </label>
  </fieldset>

  <p class="sum"><span>Subtotal</span><span>{{ formatTaka(subtotal) }}</span></p>
  <p class="sum">
    <span>Delivery</span>
    <span>{{ shipping ? formatTaka(shipping.charge_bdt) : 'Choose an area' }}</span>
  </p>
  <p class="total"><span>Total</span><span>{{ formatTaka(total) }}</span></p>

  <fieldset class="choices pay">
    <legend>Pay by</legend>
    <label v-for="option in paymentOptions" :key="option.method" class="choice">
      <input v-model="payment.method" type="radio" :name="id('payment-method')" :value="option.method" required />
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
      <label :for="id('transaction-id')">{{ wallet.label }} transaction ID</label>
      <input :id="id('transaction-id')" v-model="payment.transaction_id" autocomplete="off" autocapitalize="characters"
        minlength="6" maxlength="20" required :aria-describedby="id('transaction-help')" />
      <p :id="id('transaction-help')" class="small muted">We check it before sending your order.</p>
    </div>
  </div>

  <div class="field">
    <label :for="id('name')">Full name</label>
    <input :id="id('name')" v-model="customer.name" autocomplete="name" required />
  </div>
  <div class="field">
    <label :for="id('phone')">Phone number</label>
    <input :id="id('phone')" v-model="customer.phone" type="tel" autocomplete="tel" required />
  </div>
  <div class="field">
    <label :for="id('address')">Delivery address</label>
    <textarea :id="id('address')" v-model="customer.address" rows="3" autocomplete="street-address" required></textarea>
  </div>

  <label class="remember small">
    <input v-model="remember" type="checkbox" />
    <span v-if="account.state.customer">Save these details to my account for next time</span>
    <span v-else>Remember my details on this device for next time</span>
  </label>

  <!-- Shown just above the confirm button on the checkout page and in the chat -->
  <p class="final-warning small" role="note">
    <strong>Please check everything before you confirm:</strong> the piece, size, colour, measurements,
    address and phone number. Once your order is confirmed, it can’t be cancelled.
  </p>
</template>

<style scoped>
.choices {
  border: 0;
  padding: 0;
  margin: 0 0 16px;
}
.choices legend {
  font-weight: 600;
  margin-bottom: 8px;
  padding: 0;
}
.choice {
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
.choice input {
  width: 18px;
  height: 18px;
  padding: 0;
}
.charge {
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
.remember {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-weight: 400;
  cursor: pointer;
}
.remember input {
  width: 18px;
  height: 18px;
  padding: 0;
}
.final-warning {
  margin: 4px 0 14px;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: #fbf2dc;
  color: #6b4a05;
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
</style>
