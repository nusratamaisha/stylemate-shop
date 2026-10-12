// Browser storage can be blocked (private windows, strict settings), so never let it crash the page.

export function loadJSON(key, fallback) {
  try {
    const value = localStorage.getItem(key)
    return value ? JSON.parse(value) : fallback
  } catch {
    return fallback
  }
}

export function saveJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage unavailable: the page still works, it just won't remember after a reload.
  }
}
