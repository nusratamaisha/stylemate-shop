// Where chats with the stylist are kept: an account's by the shop (services/chat_history.py), so they
// follow the customer to another device; a guest's only in this browser. The owner never sees either.
// Both have the same functions, so stores/chat.js uses whichever it's given without caring which
// (dependency inversion: the store depends on these six functions, not on Flask or localStorage).
import { api } from '../api.js'
import { loadJSON, saveJSON } from './storage.js'

export const accountChats = {
  current: () => api('/account/chats/current'),
  saveCurrent: (chat) => api('/account/chats/current', { method: 'PUT', body: chat }),
  endCurrent: () => api('/account/chats/current/end', { method: 'POST' }),
  list: () => api('/account/chats'),
  remove: (id) => api(`/account/chats/${id}`, { method: 'DELETE' }),
  resume: (id) => api(`/account/chats/${id}/resume`, { method: 'POST' }),
}

const GUEST_CURRENT = 'stylemate-chat'
const GUEST_PAST = 'stylemate-past-chats'
const MAX_PAST_CHATS = 30 // as on the server (chat_history.MAX_PAST_CHATS)

// The list shows the customer's first message, like the server's chat_history._title()
function titleOf(messages) {
  const first = (messages.find((message) => message.role === 'customer')?.text || '').split(/\s+/).join(' ').trim()
  return (first.length > 80 ? `${first.slice(0, 79)}…` : first) || 'Chat with the stylist'
}

// A chat as the past list keeps it. DRY: used by "New chat" (endCurrent) and opening a past chat (resume)
function asPast(chat) {
  return { id: Date.now(), title: titleOf(chat.messages), ended_at: new Date().toISOString(), ...chat }
}

const pastChats = () => loadJSON(GUEST_PAST, [])

export const guestChats = {
  current: async () => loadJSON(GUEST_CURRENT, null),
  saveCurrent: async (chat) => saveJSON(GUEST_CURRENT, chat),
  async endCurrent() {
    const chat = loadJSON(GUEST_CURRENT, null)
    if (!chat?.messages?.length) return
    const ended = asPast(chat)
    saveJSON(GUEST_PAST, [ended, ...pastChats()].slice(0, MAX_PAST_CHATS))
    saveJSON(GUEST_CURRENT, null)
  },
  list: async () => pastChats().map(({ id, title, ended_at }) => ({ id, title, ended_at })),
  remove: async (id) => saveJSON(GUEST_PAST, pastChats().filter((past) => past.id !== id)),
  // Like the server's chat_history.resume_past_chat(): the two chats swap places, so the list never grows
  async resume(id) {
    const chosen = pastChats().find((past) => past.id === id)
    if (!chosen) throw new Error("That chat isn't in your history.") // the server's words too
    const current = loadJSON(GUEST_CURRENT, null)
    const others = pastChats().filter((past) => past.id !== id)
    saveJSON(GUEST_PAST, current?.messages?.length ? [asPast(current), ...others] : others)
    const chat = { messages: chosen.messages, drafts: chosen.drafts, session_id: chosen.session_id }
    saveJSON(GUEST_CURRENT, chat)
    return chat
  },
}
