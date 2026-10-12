// The shop's size guide, loaded the first time it is needed and shared by every page.
import { reactive } from 'vue'
import { api } from '../api.js'

const state = reactive({ sizes: [], sleeves: [], loaded: false, error: '' })
let loading = null

export function useSizeGuide() {
  if (!loading) {
    loading = api('/size-guide')
      .then((guide) => {
        state.sizes = guide.sizes
        state.sleeves = guide.sleeves
      })
      .catch((error) => {
        state.error = error.message
        loading = null // allow a retry the next time it is opened
      })
      .finally(() => {
        state.loaded = true
      })
  }
  return state
}
