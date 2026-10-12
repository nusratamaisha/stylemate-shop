// The shopping bag. Kept in the browser until checkout; the server recalculates every price then.
import { computed, reactive, watch } from 'vue'
import { loadJSON, saveJSON } from '../utils/storage.js'

const STORAGE_KEY = 'house-of-m-bag'

const state = reactive({ items: loadJSON(STORAGE_KEY, []) })
watch(() => state.items, (items) => saveJSON(STORAGE_KEY, items), { deep: true })

function lineKey(item) {
  return [item.product_code, item.size, item.colour, [...(item.option_ids || [])].sort().join('+'), item.notes || '', JSON.stringify(item.measurements || ''), item.reference_image || ''].join('|')
}

export function useBag() {
  return {
    items: computed(() => state.items),
    count: computed(() => state.items.reduce((sum, item) => sum + item.quantity, 0)),
    total: computed(() => state.items.reduce((sum, item) => sum + item.unit_price_bdt * item.quantity, 0)),

    add(item) {
      const key = lineKey(item)
      const existing = state.items.find((line) => line.key === key)
      if (existing) existing.quantity = Math.min(10, existing.quantity + item.quantity)
      else state.items.push({ ...item, key })
    },
    setQuantity(key, quantity) {
      const line = state.items.find((item) => item.key === key)
      if (line) line.quantity = Math.max(1, Math.min(10, quantity))
    },
    remove(key) {
      state.items = state.items.filter((item) => item.key !== key)
    },
    clear() {
      state.items = []
    },
  }
}
