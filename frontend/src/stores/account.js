// The logged-in customer, shared by every page. A guest has customer === null.
import { reactive } from 'vue'
import { api } from '../api.js'

const state = reactive({ customer: null, loaded: false })
let loading = null

function load() {
  if (!loading) {
    loading = api('/account/me')
      .then((data) => (state.customer = data.customer))
      .catch(() => (state.customer = null)) // can't reach the shop: carry on as a guest
      .finally(() => (state.loaded = true))
  }
  return loading
}

export function useAccount() {
  load()
  return {
    state,
    async register(details) {
      state.customer = (await api('/account/register', { method: 'POST', body: details })).customer
    },
    async logIn(email, password) {
      state.customer = (await api('/account/login', { method: 'POST', body: { email, password } })).customer
    },
    // Fetch the account again, e.g. after an order saved new details to it
    async refresh() {
      loading = null
      await load()
    },
    // Change or clear saved details from the account page (PATCH sends only what changed)
    async saveDetails(details) {
      state.customer = (await api('/account/details', { method: 'PATCH', body: details })).customer
    },
    async logOut() {
      await api('/account/logout', { method: 'POST' }).catch(() => {})
      state.customer = null
    },
  }
}
