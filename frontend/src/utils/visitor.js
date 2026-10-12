// A random ID kept in the browser, so Maira can tell one visitor's requests from another's.
import { loadJSON, saveJSON } from './storage.js'

const VISITOR_KEY = 'house-of-m-visitor'

export function visitorId() {
  let id = loadJSON(VISITOR_KEY, null)
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : `v-${Date.now()}-${Math.random().toString(16).slice(2)}`
    saveJSON(VISITOR_KEY, id)
  }
  return id
}
