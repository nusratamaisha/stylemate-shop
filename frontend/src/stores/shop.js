// Shop details and products, loaded once and shared by every page.
import { reactive } from 'vue'
import { api } from '../api.js'

const state = reactive({ info: null, products: [], loaded: false, error: '' })
let loading = null

export function useShop() {
  if (!loading) {
    loading = Promise.all([api('/shop'), api('/products')])
      .then(([info, products]) => {
        state.info = info
        state.products = products
      })
      .catch((error) => {
        state.error = error.message
        loading = null // allow a retry on the next page
      })
      .finally(() => {
        state.loaded = true
      })
  }
  return state
}
