<script setup>
// A customer's account: log in or sign up, then see their details and past orders.
import { reactive, ref, watch } from 'vue'
import { api } from '../api.js'
import { useAccount } from '../stores/account.js'
import { formatDate, formatTaka } from '../utils/format.js'

const account = useAccount()
const mode = ref('login') // 'login' | 'register'
const form = reactive({ name: '', email: '', phone: '', password: '' })
const busy = ref(false)
const error = ref('')

const orders = ref([])
const ordersError = ref('')
const STATUS_LABELS = { new: 'Received', in_production: 'Being made', shipped: 'Shipped' }

async function submit() {
  busy.value = true
  error.value = ''
  try {
    if (mode.value === 'register') await account.register({ ...form })
    else await account.logIn(form.email, form.password)
    form.password = ''
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function loadOrders() {
  ordersError.value = ''
  try {
    orders.value = await api('/account/orders')
  } catch (err) {
    ordersError.value = err.message
  }
}

watch(() => account.state.customer, (customer) => {
  if (customer) loadOrders()
  else orders.value = []
}, { immediate: true })
</script>

<template>
  <div class="page account">
    <template v-if="!account.state.loaded" />

    <!-- Logged in -->
    <template v-else-if="account.state.customer">
      <div class="top">
        <div>
          <h1>Hello, {{ account.state.customer.name.split(' ')[0] }}</h1>
          <p class="muted">{{ account.state.customer.email }}<span v-if="account.state.customer.phone"> · {{ account.state.customer.phone }}</span></p>
        </div>
        <button type="button" class="button secondary small" @click="account.logOut()">Log out</button>
      </div>

      <h2>Your orders</h2>
      <p v-if="ordersError" class="message error">{{ ordersError }}</p>
      <p v-else-if="!orders.length" class="muted">
        No orders yet. Orders you place while logged in appear here.
        <RouterLink to="/shop">Browse the collection</RouterLink>
      </p>

      <article v-for="order in orders" :key="order.order_id" class="order">
        <header class="order-head">
          <strong>Order {{ order.order_id }}</strong>
          <span class="muted">{{ formatDate(order.ordered_at) }}</span>
          <span class="order-total">{{ formatTaka(order.total_bdt) }}</span>
        </header>
        <ul class="items">
          <li v-for="item in order.items" :key="item.id">
            <RouterLink :to="`/products/${item.product_code}`">{{ item.product_name }}</RouterLink>
            <span class="muted"> · Size {{ item.size }}, {{ item.colour }} × {{ item.quantity }}</span>
            <p v-if="item.is_custom" class="small">
              <span class="tag custom">Made to order</span> {{ item.custom_details }} ·
              {{ STATUS_LABELS[item.status] || item.status }}<span v-if="item.ready_by">, ready around {{ formatDate(item.ready_by) }}</span>
            </p>
            <RouterLink :to="`/products/${item.product_code}#reviews`" class="small">Write a review</RouterLink>
          </li>
        </ul>
        <p class="small muted">Includes {{ formatTaka(order.shipping_bdt) }} delivery. Paid on delivery.</p>
      </article>
    </template>

    <!-- Guest -->
    <template v-else>
      <h1>{{ mode === 'login' ? 'Log in' : 'Create an account' }}</h1>
      <p class="muted">With an account you can see your past orders and review pieces you’ve bought. You can still order without one.</p>

      <form class="form" @submit.prevent="submit">
        <div v-if="mode === 'register'" class="field">
          <label for="account-name">Full name</label>
          <input id="account-name" v-model="form.name" autocomplete="name" maxlength="120" required />
        </div>
        <div class="field">
          <label for="account-email">Email</label>
          <input id="account-email" v-model="form.email" type="email" autocomplete="email" required />
        </div>
        <div v-if="mode === 'register'" class="field">
          <label for="account-phone">Phone number <span class="muted">(optional)</span></label>
          <input id="account-phone" v-model="form.phone" type="tel" autocomplete="tel" maxlength="40" />
        </div>
        <div class="field">
          <label for="account-password">Password<span v-if="mode === 'register'" class="muted"> (at least 8 characters)</span></label>
          <input id="account-password" v-model="form.password" type="password" minlength="8" required
            :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" />
        </div>

        <p v-if="error" class="message error" role="alert">{{ error }}</p>
        <button type="submit" class="button" :disabled="busy">
          {{ busy ? 'One moment…' : mode === 'login' ? 'Log in' : 'Create account' }}
        </button>
      </form>

      <p class="switch">
        <template v-if="mode === 'login'">
          New here? <button type="button" class="text-button" @click="mode = 'register'; error = ''">Create an account</button>
        </template>
        <template v-else>
          Already have an account? <button type="button" class="text-button" @click="mode = 'login'; error = ''">Log in</button>
        </template>
      </p>
    </template>
  </div>
</template>

<style scoped>
.account {
  max-width: 760px;
  padding-top: 40px;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 16px;
  margin-bottom: 32px;
}
h1 {
  margin-bottom: 4px;
}
h2 {
  font-size: var(--step-2);
  margin-bottom: 12px;
}
.form {
  max-width: 420px;
  margin-top: 24px;
}
.switch {
  margin-top: 20px;
}
.order {
  padding: 18px 0;
  border-top: 1px solid var(--line);
}
.order-head {
  display: flex;
  gap: 14px;
  align-items: baseline;
}
.order-total {
  margin-left: auto;
  font-weight: 600;
}
.items {
  margin: 10px 0;
  padding-left: 20px;
}
.items li + li {
  margin-top: 10px;
}
.items p {
  margin: 2px 0;
}
</style>
