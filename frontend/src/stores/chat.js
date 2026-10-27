// The conversation with the stylist: messages, the Maira session, and sending text or voice.
// The chat widget only displays this state; the logic lives here.
// History: the chat is saved after every change, and "New chat" moves it to the list of past chats,
// which the customer can open, read, and continue. Where they are kept: utils/chatStorage.js.
import { reactive, watch } from 'vue'
import { api } from '../api.js'
import { useAccount } from './account.js'
import { accountChats, guestChats } from '../utils/chatStorage.js'
import { applyAnswer, doneText, languageOf, matchTypedAnswer, newDraft, nextQuestion } from '../utils/chatOrder.js'
import { visitorId } from '../utils/visitor.js'

const MAX_MESSAGES = 100 // the newest ones; Flask refuses more (chat_history.MAX_MESSAGES)

const state = reactive({
  open: false,
  view: 'chat', // 'chat' | 'past' (the list of past chats)
  // { role: 'customer' | 'stylist' | 'notice', text, products?, customize?, viaVoice?,
  //   question? (a follow-up with choices), answered?, draftId? (the finished order's summary) }
  messages: [],
  drafts: {}, // orders being filled in through follow-up questions, by id (utils/chatOrder.js)
  status: 'idle', // 'idle' | 'thinking' | 'transcribing'
  sessionId: null, // Maira's session, sent back so follow-up questions have context
  pastChats: [], // { id, title, ended_at }, newest first
  historyError: '',
})

let draftCount = 0

// --- History ---

const account = useAccount()
const storage = () => (account.state.customer ? accountChats : guestChats)
let lastSaved = ''
let saving = Promise.resolve() // saves go one after another, so an older one never lands last

// What is saved: the newest messages, the orders they point to, and Maira's session (so follow-ups keep context)
function snapshot() {
  const messages = state.messages.slice(-MAX_MESSAGES)
  const used = new Set(messages.map((message) => message.draftId).filter(Boolean))
  const drafts = Object.fromEntries(Object.entries(state.drafts).filter(([id]) => used.has(Number(id))))
  return { messages, drafts, session_id: state.sessionId }
}

function show(saved) {
  state.messages = saved?.messages || []
  state.drafts = saved?.drafts || {}
  state.sessionId = saved?.session_id || null
  draftCount = Math.max(0, ...Object.keys(state.drafts).map(Number)) // new orders get new ids
  lastSaved = JSON.stringify(snapshot()) // what we just loaded needs no saving
}

// Load the right chat whenever who is chatting changes: on page load, log in, log out.
// Logging out swaps the account's chats for the guest's, so the next person at this computer can't read them.
watch(
  () => account.state.loaded && (account.state.customer?.email ?? 'guest'),
  async (who) => {
    if (!who) return // still finding out
    show(null)
    Object.assign(state, { view: 'chat', pastChats: [] })
    const saved = await storage().current().catch(() => null)
    if ((account.state.customer?.email ?? 'guest') === who) show(saved) // still the same person when it arrives
  },
  { immediate: true },
)

// Save after every change (a message, an answer, an order placed)
watch(
  () => [state.messages, state.drafts, state.sessionId],
  () => {
    if (!account.state.loaded) return
    const data = snapshot()
    const text = JSON.stringify(data)
    if (text === lastSaved) return
    lastSaved = text
    const store = storage()
    saving = saving.then(() => store.saveCurrent(data)).catch(() => {}) // not saved: the chat still works
  },
  { deep: true },
)

function addStylistReply(reply) {
  state.sessionId = reply.session_id || state.sessionId
  state.messages.push({ role: 'stylist', text: reply.answer, products: reply.products || [], customize: reply.customize || null })
  // The customer wants to order: Flask checked the product, so ask for whatever is still missing
  if (reply.order) {
    const draft = newDraft(++draftCount, reply.order, languageOf(reply.answer))
    state.drafts[draft.id] = draft
    askNext(draft)
  }
}

// Ask the next follow-up question, or show the finished order (ChatOrderCard) when nothing is missing.
function askNext(draft) {
  const question = nextQuestion(draft)
  if (question) state.messages.push({ role: 'stylist', text: question.text, question, draftId: draft.id, answered: null })
  else state.messages.push({ role: 'stylist', text: doneText(draft), draftId: draft.id })
}

function answer(message, choice) {
  if (message.answered !== null) return // each question is answered once
  message.answered = choice.label
  state.messages.push({ role: 'customer', text: choice.label })
  const draft = state.drafts[message.draftId]
  applyAnswer(draft, message.question, choice.value)
  askNext(draft)
}

// The question still waiting for an answer, if any (only the newest message can be one)
function openQuestion() {
  const last = state.messages.at(-1)
  return last?.question && last.answered === null ? last : null
}

export function useChat() {
  return {
    state,

    answer,

    // Ask the same order's questions again, e.g. after "Change my answers". A new draft,
    // so the summary already in the chat keeps showing what it showed.
    restartOrder(draftId) {
      const old = state.drafts[draftId]
      const draft = newDraft(++draftCount, old.order, old.lang)
      state.drafts[draft.id] = draft
      askNext(draft)
    },

    async ask(text) {
      const message = text.trim()
      if (!message || state.status !== 'idle') return
      // A typed answer to the open question ("M", "yellow", "no") is taken here, without asking the AI
      const open = openQuestion()
      const choice = open && matchTypedAnswer(open.question, message)
      if (choice) return answer(open, choice)
      state.messages.push({ role: 'customer', text: message })
      state.status = 'thinking'
      try {
        addStylistReply(await api('/chat', {
          method: 'POST',
          body: { message, visitor_id: visitorId(), session_id: state.sessionId },
        }))
      } catch (error) {
        state.messages.push({ role: 'notice', text: error.message })
      } finally {
        state.status = 'idle'
      }
    },

    async askByVoice(wavBlob) {
      if (state.status !== 'idle') return
      const form = new FormData()
      form.append('audio', wavBlob, 'question.wav')
      form.append('visitor_id', visitorId())
      if (state.sessionId) form.append('session_id', state.sessionId)

      state.status = 'transcribing'
      try {
        const reply = await api('/voice', { method: 'POST', form })
        if (!reply.heard) {
          state.messages.push({ role: 'notice', text: reply.message })
          return
        }
        state.messages.push({ role: 'customer', text: reply.transcript, viaVoice: true })
        addStylistReply(reply)
      } catch (error) {
        state.messages.push({ role: 'notice', text: error.message })
      } finally {
        state.status = 'idle'
      }
    },

    notice(text) {
      state.messages.push({ role: 'notice', text })
    },

    // An order confirmed inside the chat. Kept on its draft so the history shows it as placed,
    // and the "Confirm order" form can't come back and send it twice.
    // Only the reference and total: no phone, address or transaction ID goes into the history.
    markPlaced(draftId, { order_id, customer_order_number, total_bdt }) {
      state.drafts[draftId].placed = { order_id, customer_order_number, total_bdt }
    },

    // "New chat": the chat so far joins the past chats, and a fresh one starts with a new Maira session
    async newChat() {
      if (state.status !== 'idle' || !state.messages.length) return
      state.historyError = ''
      try {
        await saving // its last change is saved first
        await storage().endCurrent()
        show(null)
      } catch (error) {
        state.historyError = error.message // the chat stays as it was
      }
    },

    async showPastChats() {
      state.historyError = ''
      state.view = 'past'
      try {
        state.pastChats = await storage().list()
      } catch (error) {
        state.historyError = error.message
      }
    },

    // Opening a past chat goes back into it: it becomes the chat again, with Maira's session and any
    // unanswered order question, and the chat open now joins the list (chat_history.resume_past_chat)
    async openPastChat(id) {
      if (state.status !== 'idle') return // a reply is still on its way into the chat open now
      state.historyError = ''
      try {
        await saving // the chat open now is saved first, so it joins the list with its last message
        show(await storage().resume(id))
        state.view = 'chat'
      } catch (error) {
        state.historyError = error.message // nothing changed: the list stays open
      }
    },

    async deletePastChat(id) {
      state.historyError = ''
      try {
        await storage().remove(id)
        state.pastChats = state.pastChats.filter((chat) => chat.id !== id)
      } catch (error) {
        state.historyError = error.message
      }
    },

    backToChat() {
      Object.assign(state, { view: 'chat', historyError: '' })
    },
  }
}
