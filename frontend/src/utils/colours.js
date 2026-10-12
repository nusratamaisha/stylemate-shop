// Colour names from the product data, as fabric swatches.
// Used for colour pickers and for the swatch shown until a product has a photo.

const SWATCHES = {
  navy: '#1f2a4d',
  olive: '#6b6b3a',
  maroon: '#6e1e2b',
  emerald: '#1e6b52',
  mustard: '#d4a02a',
  white: '#f6f4f0',
  'sky blue': '#8db8da',
  black: '#1e1c1d',
  champagne: '#e9d8b8',
  teal: '#2e7c7a',
  rust: '#a9532b',
  indigo: '#2f3e6e',
  'off-white': '#eee8dc',
  beige: '#d9c7a7',
  'blush pink': '#e9b9b9',
  sage: '#a3b18a',
  sand: '#d6c29e',
  grey: '#8e8e8e',
  orange: '#e07b2e',
  gold: '#c9a445',
  red: '#b3262e',
  green: '#3f7d4e',
  blue: '#2f5d9b',
  pink: '#e48aa6',
  'dusty pink': '#d8a3a8',
  'pink floral': '#e7a3b4',
  'blue floral': '#9fb7d9',
  ivory: '#f3ecdc',
  'lemon yellow': '#f3e58a',
  'cream and lilac': '#e9e0f0',
  'denim blue': '#5f7fa6',
}

export function swatch(colourName) {
  return SWATCHES[(colourName || '').trim().toLowerCase()] || '#cfc6c2'
}

// Light swatches need a visible edge on a white page.
export function isLight(colourName) {
  const hex = swatch(colourName).slice(1)
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16))
  return 0.299 * r + 0.587 * g + 0.114 * b > 200
}
