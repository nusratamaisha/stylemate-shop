// The shopping bag. Kept in the browser until checkout; the server recalculates every price then.
// The bag remembers whose it is (`owner`: the account's email, or null for a guest), so on a shared
// computer a customer's bag never shows to the next person: logging out, or a login that has
// expired, empties it. A guest's bag is kept when they log in, so they can sign in to check out.
import { computed, reactive, watch } from 'vue'
import { useAccount } from './account.js'
import { loadJSON, saveJSON } from '../utils/storage.js'

const STORAGE_KEY = 'stylemate-bag'

function loadBag() {
  const saved = loadJSON(STORAGE_KEY, null)
  if (Array.isArray(saved)) return { owner: null, items: saved } // saved before bags had an owner
  return { owner: saved?.owner ?? null, items: Array.isArray(saved?.items) ? saved.items : [] }
}

const state = reactive(loadBag())
watch(state, () => saveJSON(STORAGE_KEY, { owner: state.owner, items: state.items }), { deep: true })

// Whenever who is shopping becomes known or changes (page load, log in, log out)
const account = useAccount()
watch(
  () => account.state.loaded && (account.state.customer?.email ?? 'guest'),
  (who) => {
    if (!who) return // still finding out
    const shopper = who === 'guest' ? null : who
    if (state.owner && state.owner !== shopper) state.items = [] // someone else's bag
    state.owner = shopper
  },
  { immediate: true },
)

// An account's bag stays hidden until we know that account is still the one logged in
const visibleItems = computed(() => (state.owner && !account.state.loaded ? [] : state.items))

function lineKey(item) {
  return [item.product_code, item.size, item.colour, [...(item.option_ids || [])].sort().join('+'), item.notes || '', JSON.stringify(item.measurements || ''), item.reference_image || ''].join('|')
}

export function useBag() {
  return {
    items: visibleItems,
    count: computed(() => visibleItems.value.reduce((sum, item) => sum + item.quantity, 0)),
    total: computed(() => visibleItems.value.reduce((sum, item) => sum + item.unit_price_bdt * item.quantity, 0)),

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
