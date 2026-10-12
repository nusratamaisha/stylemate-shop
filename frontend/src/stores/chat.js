// The conversation with the stylist: messages, the Maira session, and sending text or voice.
// The chat widget only displays this state; the logic lives here.
import { reactive } from 'vue'
import { api } from '../api.js'
import { loadJSON, saveJSON } from '../utils/storage.js'
import { visitorId } from '../utils/visitor.js'

const state = reactive({
  open: false,
  messages: [], // { role: 'customer' | 'stylist' | 'notice', text, products?, order?, viaVoice? }
  status: 'idle', // 'idle' | 'thinking' | 'transcribing'
  sessionId: null, // Maira's session, sent back so follow-up questions have context
})

function addStylistReply(reply) {
  state.sessionId = reply.session_id || state.sessionId
  // order: a piece the customer confirmed in chat and Flask checked; the widget shows a checkout link for it
  state.messages.push({ role: 'stylist', text: reply.answer, products: reply.products || [], order: reply.order || null, customize: reply.customize || null })
}

export function useChat() {
  return {
    state,

    async ask(text) {
      const message = text.trim()
      if (!message || state.status !== 'idle') return
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
