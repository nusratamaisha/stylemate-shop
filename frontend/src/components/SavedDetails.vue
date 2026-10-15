<script setup>
// "My details" on the account page: what the shop remembers for checkout, which the customer
// can change or clear. Saved by Flask after an order with "remember" ticked (accounts.remember_details).
import { computed, reactive, ref, watch } from 'vue'
import { useAccount } from '../stores/account.js'
import { useShop } from '../stores/shop.js'

const account = useAccount()
const shop = useShop()
const form = reactive({ name: '', phone: '', address: '', delivery_area: '', payment_method: '' })
const saving = ref(false)
const message = ref('')
const error = ref('')

// Start from what is saved, and again whenever the account changes (an order may have updated it)
watch(() => account.state.customer, (customer) => {
  if (customer) for (const key of Object.keys(form)) form[key] = customer[key] || ''
}, { immediate: true })

const MEASUREMENT_WORDS = { bust: 'bust', waist: 'waist', sleeve_length: 'sleeve length', length: 'length' }
const measurementsText = computed(() => Object.entries(account.state.customer?.measurements || {})
  .map(([key, inches]) => `${MEASUREMENT_WORDS[key] || key} ${inches} in`).join(', '))

async function save(details, done) {
  saving.value = true
  message.value = error.value = ''
  try {
    await account.saveDetails(details)
    message.value = done
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="details" aria-labelledby="details-title">
    <h2 id="details-title">My details</h2>
    <p class="muted small">Filled in for you at checkout, so you don’t type them every time.</p>

    <form class="form" @submit.prevent="save({ ...form }, 'Your details are saved.')">
      <div class="grid">
        <div class="field">
          <label for="details-name">Full name</label>
          <input id="details-name" v-model="form.name" autocomplete="name" maxlength="120" required />
        </div>
        <div class="field">
          <label for="details-phone">Phone number</label>
          <input id="details-phone" v-model="form.phone" type="tel" autocomplete="tel" maxlength="40" />
        </div>
      </div>
      <div class="field">
        <label for="details-address">Delivery address</label>
        <textarea id="details-address" v-model="form.address" rows="2" autocomplete="street-address" maxlength="500"></textarea>
      </div>
      <div class="grid">
        <div class="field">
          <label for="details-area">Deliver to</label>
          <select id="details-area" v-model="form.delivery_area">
            <option value="">Not saved</option>
            <option v-for="option in shop.info?.shipping || []" :key="option.area" :value="option.area">{{ option.label }}</option>
          </select>
        </div>
        <div class="field">
          <label for="details-payment">Usually pay by</label>
          <select id="details-payment" v-model="form.payment_method">
            <option value="">Not saved</option>
            <option v-for="option in shop.info?.payment || []" :key="option.method" :value="option.method">{{ option.label }}</option>
          </select>
        </div>
      </div>
      <button type="submit" class="button small" :disabled="saving">{{ saving ? 'Saving…' : 'Save my details' }}</button>
    </form>

    <div class="fit">
      <h3>Your size and measurements</h3>
      <p v-if="!account.state.customer.preferred_size && !measurementsText" class="muted small">
        Nothing saved yet. Your size and measurements are remembered from your orders.
      </p>
      <template v-else>
        <p v-if="account.state.customer.preferred_size" class="small">Usual size: <strong>{{ account.state.customer.preferred_size }}</strong></p>
        <p v-if="measurementsText" class="small">Measurements: {{ measurementsText }}</p>
        <p class="muted small">We use them to suggest your size, and soon to recommend pieces that fit you.</p>
        <button type="button" class="text-button small" :disabled="saving"
          @click="save({ preferred_size: '', measurements: null }, 'Your size and measurements are forgotten.')">
          Forget my size and measurements
        </button>
      </template>
    </div>

    <p v-if="message" class="message ok" role="status">{{ message }}</p>
    <p v-if="error" class="message error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.details {
  margin: 8px 0 40px;
  padding: 24px;
  border-radius: var(--radius-large);
  background: var(--jamdani);
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
.fit {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
}
.fit h3 {
  font-size: var(--step-0);
  margin: 0 0 6px;
}
.fit p {
  margin: 0 0 6px;
}
@media (max-width: 600px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
