// Checkout details remembered so a returning customer doesn't type them again.
// With an account they live in the shop's database (Customer row, saved by Flask when an
// order is placed with "remember" ticked). A guest's live only in this browser, on this
// device: they never reach the shop until the guest places an order.
import { loadJSON, saveJSON } from './storage.js'

const DEVICE_KEY = 'closet-corner-details'

// What a guest's browser remembers: { name, phone, address, delivery_area, payment_method } or null
export const deviceDetails = () => loadJSON(DEVICE_KEY, null)

export function rememberOnDevice(customer, payment) {
  const { name, phone, address, delivery_area } = customer
  saveJSON(DEVICE_KEY, { name, phone, address, delivery_area, payment_method: payment.method })
}

export function forgetOnDevice() {
  saveJSON(DEVICE_KEY, null)
}

// Fill only empty fields, so nothing the customer already typed is overwritten
export function fillIn(customer, payment, saved) {
  if (!saved) return
  for (const key of ['name', 'phone', 'address', 'delivery_area']) customer[key] ||= saved[key] || ''
  payment.method ||= saved.payment_method || ''
}

// After a successful order: a guest's browser remembers (or forgets) them; an account was
// already updated by Flask, so it's fetched again.
export async function afterOrder(account, customer, payment, remember) {
  if (account.state.customer) return account.refresh()
  if (remember) rememberOnDevice(customer, payment)
  else forgetOnDevice()
}
