<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'

const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function logIn() {
  error.value = ''
  busy.value = true
  try {
    await api('/owner/login', { method: 'POST', body: { email: email.value, password: password.value } })
    router.push('/owner')
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <form class="login" @submit.prevent="logIn">
      <h1>Shop owner login</h1>
      <p class="muted">See what customers ask, manage custom orders and update products.</p>
      <div class="field">
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" autocomplete="username" required />
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input id="password" v-model="password" type="password" autocomplete="current-password" required />
      </div>
      <p v-if="error" class="message error">{{ error }}</p>
      <button type="submit" class="button" :disabled="busy">{{ busy ? 'Logging in…' : 'Log in' }}</button>
    </form>
  </div>
</template>

<style scoped>
.login {
  max-width: 400px;
  margin: 64px auto 0;
}
.login h1 {
  font-size: var(--step-3);
}
</style>
