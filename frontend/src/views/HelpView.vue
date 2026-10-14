<script setup>
// Help: common questions, how to reach the shop, and a form that sends a message to the owner.
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api.js'
import { useChat } from '../stores/chat.js'

const chat = useChat()
const faq = ref([])
const contact = ref(null)
const loadError = ref('')

const form = reactive({ name: '', contact: '', message: '' })
const sending = ref(false)
const sent = ref(false)
const sendError = ref('')
// An optional photo, for example a wrong size being measured. Only the owner can open it.
const photoInput = ref(null)
const MAX_PHOTO_BYTES = 4 * 1024 * 1024 // the server checks this too

onMounted(async () => {
  try {
    const data = await api('/help')
    faq.value = data.faq
    contact.value = data.contact
  } catch (error) {
    loadError.value = error.message
  }
})

async function send() {
  sendError.value = ''
  sent.value = false
  const photo = photoInput.value?.files?.[0]
  if (photo && photo.size > MAX_PHOTO_BYTES) {
    sendError.value = 'That photo is too large (4 MB maximum).'
    return
  }
  // Sent as a form, not JSON, so the photo can travel with the message
  const data = new FormData()
  Object.entries(form).forEach(([name, value]) => data.append(name, value))
  if (photo) data.append('picture', photo)

  sending.value = true
  try {
    await api('/contact', { method: 'POST', form: data })
    sent.value = true
    Object.assign(form, { name: '', contact: '', message: '' })
    photoInput.value.value = ''
  } catch (error) {
    sendError.value = error.message
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="page help">
    <h1>Help</h1>
    <p class="muted">
      Answers to common questions, and how to reach us.
      <button type="button" class="text-button" @click="chat.state.open = true">Or ask the stylist about our clothes.</button>
    </p>

    <p v-if="loadError" class="message error">{{ loadError }}</p>

    <section v-if="faq.length" aria-labelledby="faq-title">
      <h2 id="faq-title">Frequently asked questions</h2>
      <details v-for="item in faq" :key="item.id" class="question">
        <summary>{{ item.question }}</summary>
        <p>{{ item.answer }}</p>
      </details>
      <p class="small"><RouterLink to="/size-guide">Open the size guide</RouterLink></p>
    </section>

    <section id="contact" aria-labelledby="contact-title">
      <h2 id="contact-title">Contact us</h2>
      <div class="contact">
        <dl v-if="contact" class="details">
          <div v-if="contact.phone"><dt>Phone</dt><dd><a :href="`tel:${contact.phone.replace(/[^+\d]/g, '')}`">{{ contact.phone }}</a></dd></div>
          <div v-if="contact.email"><dt>Email</dt><dd><a :href="`mailto:${contact.email}`">{{ contact.email }}</a></dd></div>
          <div v-if="contact.address"><dt>Address</dt><dd>{{ contact.address }}</dd></div>
          <div v-if="contact.hours"><dt>Hours</dt><dd>{{ contact.hours }}</dd></div>
        </dl>

        <form class="form" @submit.prevent="send">
          <h3>Send us a message</h3>
          <div class="field">
            <label for="contact-name">Your name</label>
            <input id="contact-name" v-model="form.name" type="text" maxlength="120" required autocomplete="name" />
          </div>
          <div class="field">
            <label for="contact-reply">Phone or email, so we can reply</label>
            <input id="contact-reply" v-model="form.contact" type="text" maxlength="200" required />
          </div>
          <div class="field">
            <label for="contact-message">Message</label>
            <textarea id="contact-message" v-model="form.message" rows="4" maxlength="1000" required></textarea>
          </div>
          <div class="field">
            <label for="contact-photo">Photo <span class="muted">(optional)</span></label>
            <input id="contact-photo" ref="photoInput" type="file" accept="image/jpeg,image/png,image/webp" aria-describedby="contact-photo-help" />
            <p id="contact-photo-help" class="small muted">
              If we sent the wrong size, lay the piece flat, measure it with a tape and attach a photo that shows the number.
              JPG, PNG or WebP, up to 4 MB.
            </p>
          </div>
          <button type="submit" class="button" :disabled="sending">{{ sending ? 'Sending…' : 'Send message' }}</button>
          <p v-if="sendError" class="message error" role="alert">{{ sendError }}</p>
          <p v-if="sent" class="message ok" role="status">Thank you. We’ve received your message and will reply soon.</p>
        </form>
      </div>
    </section>
  </div>
</template>

<style scoped>
.help {
  max-width: 860px;
  padding-top: 40px;
}
h1 {
  margin-bottom: 4px;
}
section {
  margin-top: 40px;
}
h2 {
  font-size: var(--step-2);
  margin-bottom: 12px;
}
h3 {
  font-size: var(--step-1);
  margin-bottom: 12px;
}
.question {
  border-bottom: 1px solid var(--line);
}
.question summary {
  padding: 14px 0;
  font-weight: 600;
  cursor: pointer;
}
.question p {
  margin: 0 0 16px;
  max-width: 65ch;
}
.contact {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 32px;
  align-items: start;
}
.details {
  display: grid;
  gap: 14px;
  margin: 0;
}
.details dt {
  font-weight: 600;
}
.details dd {
  margin: 0;
}
.form {
  padding: 24px;
  border-radius: 10px;
  background: var(--jamdani);
}
@media (max-width: 700px) {
  .contact {
    grid-template-columns: 1fr;
  }
}
</style>
