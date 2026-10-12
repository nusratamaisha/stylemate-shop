// Formatting shared by every page.

const taka = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

export function formatTaka(amount) {
  return `৳${taka.format(amount ?? 0)}`
}

// A change to the price: "+৳200" for an extra, "−৳100" for a reduction.
export function formatPriceChange(amount) {
  return `${amount < 0 ? '−' : '+'}${formatTaka(Math.abs(amount ?? 0))}`
}

export function formatDate(isoDate) {
  if (!isoDate) return ''
  return new Date(isoDate).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function readyDate(days) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
}
