// The conversation with the stylist: messages, the Maira session, and sending text or voice.
// The chat widget only displays this state; the logic lives here.
import { reactive } from 'vue'
import { api } from '../api.js'
import { applyAnswer, doneText, languageOf, matchTypedAnswer, newDraft, nextQuestion } from '../utils/chatOrder.js'
import { loadJSON, saveJSON } from '../utils/storage.js'
import { visitorId } from '../utils/visitor.js'

const state = reactive({
  open: false,
  // { role: 'customer' | 'stylist' | 'notice', text, products?, customize?, viaVoice?,
  //   question? (a follow-up with choices), answered?, draftId? (the finished order's summary) }
  messages: [],
  drafts: {}, // orders being filled in through follow-up questions, by id (utils/chatOrder.js)
  status: 'idle', // 'idle' | 'thinking' | 'transcribing'
  sessionId: null, // Maira's session, sent back so follow-up questions have context
})

let draftCount = 0

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
  }
}
