<script setup>
// "See it first": a generated picture of the piece with the chosen changes. Without a photo it
// shows the piece alone (no person); with the customer's photo it shows the chosen size on them.
// A preview only; the price comes from Flask. On a piece that can be made to order, the customer
// can send the picture to the tailor as their reference picture (Flask saves it: /previews/keep).
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'
import { visitorId } from '../utils/visitor.js'

const emit = defineEmits(['use-as-reference'])

const props = defineProps({
  product: { type: Object, required: true },
  colour: { type: String, default: '' },
  optionIds: { type: Array, default: () => [] },
  size: { type: String, default: '' },
  madeToMeasure: { type: Boolean, default: false },
  measurements: { type: Object, default: null }, // { bust, waist, sleeve_length, length } for a made-to-measure piece
})

const MAX_PHOTO_BYTES = 4 * 1024 * 1024

const wish = ref('')
const photo = ref(null)
const photoInput = ref(null)
const loading = ref(false)
const error = ref('')
const preview = ref(null)
const sending = ref(false)
const sentFor = ref('') // the picture last sent to the tailor, so the button says so

// A try-on shows how one size fits, so it needs a size (or a made-to-measure piece, which has none).
const needsSize = computed(() => Boolean(photo.value) && !props.size && !props.madeToMeasure)
const canAsk = computed(() => !loading.value && !needsSize.value &&
  (props.optionIds.length > 0 || wish.value.trim() || photo.value))
// The picture shows the choices made when it was drawn. Say so once they change.
const outdated = computed(() => preview.value && preview.value.madeFor !== choiceKey())

function choiceKey() {
  return JSON.stringify([props.colour, props.optionIds, wish.value.trim(), photo.value?.name || '',
    photo.value ? [props.size, props.measurements] : null]) // the size only shows in a picture on the customer
}

function choosePhoto(event) {
  const file = event.target.files[0] || null
  error.value = ''
  if (file && file.size > MAX_PHOTO_BYTES) {
    error.value = 'That photo is too large (4 MB maximum).'
    clearPhoto()
    return
  }
  photo.value = file
}

function clearPhoto() {
  photo.value = null
  if (photoInput.value) photoInput.value.value = ''
}

async function generate() {
  if (!canAsk.value) return
  const madeFor = choiceKey()
  const form = new FormData()
  form.append('visitor_id', visitorId())
  form.append('colour', props.colour)
  props.optionIds.forEach((id) => form.append('option_ids', id))
  form.append('wish', wish.value.trim())
  if (photo.value) {
    form.append('photo', photo.value)
    form.append('size', props.madeToMeasure ? '' : props.size)
    Object.entries(props.measurements || {}).forEach(([name, inches]) => form.append(name, inches))
  }

  loading.value = true
  error.value = ''
  try {
    const result = await api(`/products/${encodeURIComponent(props.product.code)}/preview`, { method: 'POST', form })
    preview.value = { ...result, madeFor }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function sendToTailor() {
  if (!preview.value || sending.value) return
  sending.value = true
  error.value = ''
  try {
    const { reference_image: name } = await api('/previews/keep', { method: 'POST', body: { token: preview.value.keep_token } })
    emit('use-as-reference', { name, previewUrl: preview.value.image_url })
    sentFor.value = preview.value.image_url
  } catch (err) {
    error.value = err.message
  } finally {
    sending.value = false
  }
}

watch(() => props.product.code, () => {
  preview.value = null
  error.value = ''
  sentFor.value = ''
})
</script>

<template>
  <section class="preview" aria-labelledby="preview-title">
    <h2 id="preview-title" class="title">See it first</h2>

    <div v-if="product.customizable" class="field">
      <label for="preview-wish">Describe an idea <span class="muted">(optional)</span></label>
      <textarea id="preview-wish" v-model="wish" rows="2" maxlength="200"
        placeholder="For example: a gold border at the hem"></textarea>
      <p class="muted small hint">Ideas typed here appear in the picture only. Like the result? Send the picture to the tailor below, and we’ll confirm the idea with you.</p>
    </div>

    <div class="field">
      <label for="preview-photo">Your photo <span class="muted">(optional)</span></label>
      <input id="preview-photo" ref="photoInput" type="file" accept="image/jpeg,image/png,image/webp" @change="choosePhoto" />
      <p class="muted small hint">
        A clear, full-length photo works best. It is sent to our picture service to make this preview and is not saved by the shop.
        <button v-if="photo" type="button" class="text-button" @click="clearPhoto">Remove photo</button>
      </p>
    </div>

    <p v-if="needsSize" class="message error" role="status">Choose a size above, so the picture can show how that size fits you.</p>
    <button type="button" class="button secondary" :disabled="!canAsk" @click="generate">
      {{ loading ? 'Drawing your preview…' : preview ? 'Draw it again' : 'Show me' }}
    </button>
    <p v-if="loading" class="muted small" role="status">This can take up to a minute.</p>
    <p v-if="error" class="message error" role="alert">{{ error }}</p>

    <figure v-if="preview" class="result">
      <img :src="preview.image_url" :alt="`Preview of ${product.name}${preview.details ? ' with ' + preview.details : ''}`" />
      <figcaption class="small">
        <span v-if="outdated" class="outdated">You’ve changed your choices since this picture was drawn. </span>
        <span class="muted">An AI-drawn preview: the finished piece may look different. The price above is what you pay.</span>
      </figcaption>
      <div v-if="product.customizable" class="send">
        <p v-if="sentFor === preview.image_url" class="message ok small" role="status">
          Sent to the tailor. It’s now your reference picture under “Make it yours”.
        </p>
        <button v-else type="button" class="button secondary small" :disabled="sending" @click="sendToTailor">
          {{ sending ? 'Sending…' : 'Send this picture to the tailor' }}
        </button>
        <p class="muted small hint">It goes with pieces made to order, so add your measurements above.</p>
      </div>
    </figure>
  </section>
</template>

<style scoped>
.preview {
  margin-top: 20px;
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: var(--radius-large);
  background: #fff;
}
.title {
  font-size: var(--step-2);
  margin-bottom: 4px;
}
.field {
  margin: 16px 0;
}
.hint {
  margin: 6px 0 0;
}
.result {
  margin: 20px 0 0;
}
.result img {
  display: block;
  width: 100%;
  border-radius: var(--radius);
}
figcaption {
  margin-top: 8px;
}
.send {
  margin-top: 14px;
}
.send .message {
  margin: 0;
}
.outdated {
  color: var(--danger);
}
</style>
