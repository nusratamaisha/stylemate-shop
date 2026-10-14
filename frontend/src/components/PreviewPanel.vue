<script setup>
// "See it first": a generated picture of the piece with the chosen changes. Without a photo it
// shows the piece alone (no person); with the customer's photo it shows the chosen size on them.
// A preview only; the price comes from Flask.
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'
import { visitorId } from '../utils/visitor.js'

const props = defineProps({
  product: { type: Object, required: true },
  colour: { type: String, default: '' },
  optionIds: { type: Array, default: () => [] },
  size: { type: String, default: '' },
  madeToMeasure: { type: Boolean, default: false },
  measurements: { type: Object, default: null }, // { bust, waist, hip, length } for a made-to-measure piece
})

const MAX_PHOTO_BYTES = 4 * 1024 * 1024

const wish = ref('')
const photo = ref(null)
const photoInput = ref(null)
const loading = ref(false)
const error = ref('')
const preview = ref(null)

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

watch(() => props.product.code, () => {
  preview.value = null
  error.value = ''
})
</script>

<template>
  <section class="preview" aria-labelledby="preview-title">
    <h2 id="preview-title" class="title">See it first</h2>
    <p class="muted small">
      Get a picture of this piece on its own in {{ colour || 'your colour' }}<span v-if="product.customizable"> with the changes you chose above</span>.
      Add your photo to see the size you chose on you.
    </p>

    <div v-if="product.customizable" class="field">
      <label for="preview-wish">Describe an idea <span class="muted">(optional)</span></label>
      <textarea id="preview-wish" v-model="wish" rows="2" maxlength="200"
        placeholder="For example: a gold border at the hem"></textarea>
      <p class="muted small hint">Ideas typed here appear in the picture only. To order one, add it to your notes above and we’ll confirm it with you.</p>
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
    </figure>
  </section>
</template>

<style scoped>
.preview {
  margin-top: 24px;
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
  margin-top: 16px;
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
.outdated {
  color: var(--danger);
}
</style>
