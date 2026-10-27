<script setup>
// "Make it yours": the customer types their measurements and sees the price, which Flask calculates.
// There are no sleeve, length or fit buttons (Oct 15): typing any measurement makes the piece
// made to measure, and Flask works out the sleeve and length charges from the numbers
// (pricing.measured_options()). Leaving every box empty orders a standard size.
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'
import { useAccount } from '../stores/account.js'
import { useSizeGuide } from '../stores/sizeGuide.js'
import { formatPriceChange, formatTaka, readyDate } from '../utils/format.js'

const props = defineProps({
  product: { type: Object, required: true },
})
const emit = defineEmits(['change', 'use-size'])
const route = useRoute()
const sizeGuide = useSizeGuide()
const account = useAccount()
// Measurements saved from the customer's last made-to-measure order. Offered, not filled in:
// typing any measurement makes the piece made to measure, so that stays the customer's choice.
const savedMeasurements = computed(() => account.state.customer?.measurements || {})
function useSavedMeasurements() {
  for (const { key } of MEASUREMENTS) measurements[key] = savedMeasurements.value[key] ?? ''
}

// Same ranges as the server (pricing.MEASUREMENTS); the server checks them again
const MEASUREMENTS = [
  { key: 'bust', label: 'Bust', required: true, min: 20, max: 72 },
  { key: 'waist', label: 'Waist', required: false, min: 20, max: 72 },
  { key: 'sleeve_length', label: 'Sleeve length', required: false, min: 0, max: 25 },
  { key: 'length', label: 'Length', required: false, min: 20, max: 58 },
]

// A number box still lets you type "-", "+" and "e" (as in 1e5); measurements never need them
function blockSigns(event) {
  if (['-', '+', 'e', 'E'].includes(event.key)) event.preventDefault()
}

// The message under a box when its number is outside the range, so the customer knows why
function rangeError(item) {
  const value = measurements[item.key]
  if (value === '' || value === null) return ''
  const inches = Number(value)
  return inches < item.min || inches > item.max ? `Between ${item.min} and ${item.max} inches` : ''
}


const measurements = reactive({ bust: '', waist: '', sleeve_length: '', length: '' })
// A change the stylist chat handed over that no number can say, such as "Sleeveless" (see applyFromAddress)
const chatOptionIds = ref([])
const notes = ref('')
// A picture for the tailor: uploaded when chosen, because the bag can't hold a file
const picture = ref(null) // { name (from the server), filename, previewUrl }
const pictureInput = ref(null)
const uploadingPicture = ref(false)
const pictureError = ref('')
const quote = ref(null)
const error = ref('')

const cleanMeasurements = computed(() => Object.fromEntries(
  Object.entries(measurements).filter(([, value]) => value !== '' && value !== null).map(([key, value]) => [key, Number(value)])))
// Only numbers in range are priced, so a half-typed "3" on the way to "36" doesn't flash an error
const validMeasurements = computed(() => Object.fromEntries(MEASUREMENTS
  .filter(({ key, min, max }) => cleanMeasurements.value[key] >= min && cleanMeasurements.value[key] <= max)
  .map(({ key }) => [key, cleanMeasurements.value[key]])))
const madeToMeasure = computed(() => Object.keys(cleanMeasurements.value).length > 0)
const measurementsComplete = computed(() => MEASUREMENTS.every(({ key, required, min, max }) => {
  const value = cleanMeasurements.value[key]
  return value === undefined ? !required : value >= min && value <= max
}))
const measurementsText = computed(() => MEASUREMENTS.filter(({ key }) => cleanMeasurements.value[key] !== undefined)
  .map(({ key, label }) => `${label.toLowerCase()} ${cleanMeasurements.value[key]} in`).join(', '))

// The options Flask chose (made to measure, sleeves, length), sent with the order; checkout works them out again
const optionIds = computed(() => (quote.value?.is_custom ? quote.value.extras.map((extra) => extra.id) : []))

// Smart check: if a standard size already fits these measurements, say so. It ships now instead of being sewn.
const standardSize = computed(() => {
  const { bust, waist, sleeve_length: sleeve, length } = cleanMeasurements.value
  if (!madeToMeasure.value || !bust) return null
  // The waist is optional, so it is compared only when given
  const fits = sizeGuide.sizes.filter((row) => props.product.sizes.includes(row.size))
    .find((row) => row.bust_inches >= bust && (!waist || row.waist_inches >= waist))
  if (!fits) return { size: null }
  // "Fits" means every measurement given is within 2 inches of the size, not just smaller than it
  const close = fits.bust_inches - bust <= 2 && (!waist || fits.waist_inches - waist <= 2)
  // A changed length or sleeve length can only be sewn to order
  const sameLength = (!length || length === props.product.length_inches) && sleeve === undefined  // 0 = sleeveless
  return { size: fits.size, close, sameLength }
})

let requestNumber = 0
let typingTimer = null
async function refreshQuote() {
  const thisRequest = ++requestNumber
  error.value = ''
  const measured = Object.keys(validMeasurements.value).length > 0
  if (!measured && !chatOptionIds.value.length) {
    quote.value = null // nothing to make: the standard piece at its listed price
    return
  }
  try {
    const result = await api('/price-quote', {
      method: 'POST',
      body: { product_code: props.product.code, option_ids: chatOptionIds.value, measurements: measured ? validMeasurements.value : null },
    })
    if (thisRequest === requestNumber) quote.value = result // ignore answers to older requests
  } catch (err) {
    if (thisRequest === requestNumber) error.value = err.message
  }
}
// Wait until the customer pauses typing, so each keystroke isn't a request
watch([validMeasurements, chatOptionIds], () => {
  clearTimeout(typingTimer)
  typingTimer = setTimeout(refreshQuote, 300)
})

watch([quote, notes, optionIds, cleanMeasurements, picture], () => {
  emit('change', {
    quote: quote.value,
    optionIds: optionIds.value,
    notes: notes.value.trim(),
    referenceImage: picture.value?.name || '',
    madeToMeasure: madeToMeasure.value,
    measurements: madeToMeasure.value ? cleanMeasurements.value : null,
    measurementsComplete: !madeToMeasure.value || measurementsComplete.value,
    measurementsText: madeToMeasure.value ? measurementsText.value : '',
  })
})

async function choosePicture(event) {
  const file = event.target.files[0]
  pictureError.value = ''
  if (!file) return
  if (file.size > 4 * 1024 * 1024) {
    pictureError.value = 'That picture is too large (4 MB maximum).'
    pictureInput.value.value = ''
    return
  }
  const form = new FormData()
  form.append('picture', file)
  uploadingPicture.value = true
  try {
    const { reference_image: name } = await api('/reference-pictures', { method: 'POST', form })
    removePicture()
    picture.value = { name, filename: file.name, previewUrl: URL.createObjectURL(file) }
  } catch (err) {
    pictureError.value = err.message
  } finally {
    uploadingPicture.value = false
    pictureInput.value.value = ''
  }
}

function removePicture() {
  if (picture.value?.previewUrl.startsWith('blob:')) URL.revokeObjectURL(picture.value.previewUrl)
  picture.value = null
}

// A "See it first" picture the customer sent to the tailor (already saved by Flask, see PreviewPanel)
function usePicture({ name, previewUrl }) {
  removePicture()
  picture.value = { name, filename: 'Your “See it first” picture', previewUrl }
  pictureError.value = ''
}
defineExpose({ usePicture })

// The price box names only what changes for sleeves and length; the order keeps the full wording for the tailor
function priceLabel(extra) {
  return ['Sleeves', 'Length'].includes(extra.group) ? `${extra.group}:` : extra.description || extra.label
}

function useStandardSize(size) {
  for (const key of Object.keys(measurements)) measurements[key] = ''
  emit('use-size', size)
}

// Arriving from the stylist chat: the changes the customer described are in the address,
// e.g. ?sleeves=Sleeveless&bust=38&length=36. Fill them in; the price is still worked out by Flask.
function applyFromAddress() {
  const query = route.query
  const sleeves = props.product.customization.flatMap((group) => group.options).find((option) => option.label === query.sleeves)
  if (sleeves) chatOptionIds.value = [sleeves.id]
  for (const { key } of MEASUREMENTS) {
    if (query[key]) measurements[key] = Number(query[key]) || ''
  }
  refreshQuote()
}
applyFromAddress()
</script>

<template>
  <section class="customize" aria-labelledby="customize-title">
    <h2 id="customize-title" class="title">Make it yours</h2>
    <p class="muted small">
      Type your measurements and we sew it to fit you. Longer sleeves or a longer length
      cost a little more, shorter ones a little less: the price updates as you type.
    </p>

    <fieldset class="group measure">
      <legend>Your measurements <span class="current">in inches</span></legend>
      <p v-if="Object.keys(savedMeasurements).length" class="small saved">
        <button type="button" class="text-button" @click="useSavedMeasurements">Use my saved measurements</button>
      </p>
      <div class="measure-grid">
        <div v-for="item in MEASUREMENTS" :key="item.key" class="measure">
          <label :for="`measure-${item.key}`">
            {{ item.label }}
            
          </label>
            <input :id="`measure-${item.key}`" v-model="measurements[item.key]" type="number" inputmode="numeric"
            :min="item.min" :max="item.max" step="1" @keydown="blockSigns"
            :placeholder="item.key === 'length' && product.length_inches ? String(product.length_inches) : ''" />
          <span v-if="rangeError(item)" class="range-error" role="alert">{{ rangeError(item) }}</span>
        </div>
      </div>
      <p class="muted small hint">
        Measure your body, not a garment. Only the bust is needed; add the others if you want them changed.
        Leave length empty to keep it as shown<span v-if="product.length_inches"> ({{ product.length_inches }} in)</span>.
        Sleeve length is from the shoulder seam to where the sleeve should end.
        Leave every box empty to order a standard size.
      </p>

      <p v-if="standardSize?.size && standardSize.close && standardSize.sameLength" class="tip small" role="status">
        Good news: these measurements match our size <strong>{{ standardSize.size }}</strong>.
        <button type="button" class="text-button" @click="useStandardSize(standardSize.size)">
          Order size {{ standardSize.size }} ready-made
        </button>
        and it ships without the sewing wait, or keep made to measure for an exact fit.
      </p>
      <p v-else-if="standardSize && !standardSize.size" class="tip small" role="status">
        None of this piece’s standard sizes fits these measurements, so made to measure is the right choice.
      </p>
    </fieldset>

    <div class="field">
      <label for="custom-notes">Notes for the tailor <span class="muted">(optional)</span></label>
      <textarea id="custom-notes" v-model="notes" rows="2" maxlength="500"
        placeholder="For example: a little loose at the waist"></textarea>

      <div class="picture">
        <label for="custom-picture">Reference picture for the tailor <span class="muted">(optional)</span></label>
        <div v-if="picture" class="picture-chosen">
          <img :src="picture.previewUrl" alt="Your reference picture" />
          <span class="small">{{ picture.filename }}</span>
          <button type="button" class="text-button small" @click="removePicture">Remove</button>
        </div>
        <input v-else id="custom-picture" ref="pictureInput" type="file" accept="image/jpeg,image/png,image/webp"
          :disabled="uploadingPicture" @change="choosePicture" />
        <p class="muted small hint">
          {{ uploadingPicture ? 'Uploading…' : 'A photo or sketch of the detail you want, or a picture from “See it first” below. Only the shop can see it.' }}
        </p>
        <p v-if="pictureError" class="message error" role="alert">{{ pictureError }}</p>
      </div>

      <!-- The price comes only from the measurements, never from what is typed or attached here. -->
      <p v-if="(notes.trim() || picture) && !optionIds.length" class="notes-warning small" role="status">
        Your note or picture isn’t sent yet. They go with pieces made to order, so add your measurements above.
        Without them, you get the standard size at the listed price.
      </p>
    </div>

    <p v-if="error" class="message error">{{ error }}</p>
    <div v-else-if="quote" class="summary" aria-live="polite">
      <div class="line"><span>{{ product.name }}</span><span>{{ formatTaka(quote.base_price_bdt) }}</span></div>
      <div v-for="extra in quote.extras" :key="extra.id" class="line">
        <span>{{ priceLabel(extra) }}</span><span>{{ extra.extra_price_bdt ? formatPriceChange(extra.extra_price_bdt) : 'Free' }}</span>
      </div>
      <div class="line total"><span>Total</span><span>{{ formatTaka(quote.total_bdt) }}</span></div>
      <p v-if="quote.is_custom" class="ready small">
        Made to order: ready in about {{ quote.ready_in_days }} days (around {{ readyDate(quote.ready_in_days) }}).
      </p>
    </div>
  </section>
</template>

<style scoped>
.customize {
  margin-top: 28px;
  padding: 24px;
  border-radius: var(--radius-large);
  background: var(--jamdani);
}
.title {
  font-size: var(--step-2);
  margin-bottom: 4px;
}
.group {
  border: 0;
  padding: 0;
  margin: 14px 0 0;
}
legend {
  font-weight: 600;
  margin-bottom: 8px;
  padding: 0;
}
.current {
  color: var(--muted);
  font-weight: 400;
}
.current {
  margin-left: 6px;
}
.picture {
  margin-top: 14px;
}
.picture-chosen {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #fff;
}
.picture-chosen img {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
}
.picture-chosen .text-button {
  margin-left: auto;
}
.measure-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}
.measure {
  display: grid;
  grid-template-rows: auto auto;
  gap: 4px;
}
.measure label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin: 0;
  font-size: var(--step--1);
  font-weight: 600;
  white-space: nowrap;
}
.measure input {
  width: 100%;
  margin: 0;
  background: #fff;
}
.tag-note {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--muted);
}
.tag-note.needed {
  color: var(--kohl);
}
.saved {
  margin: 0 0 8px;
}
.hint {
  margin: 8px 0 0;
}
.tip {
  margin: 10px 0 0;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: #e9f3ee;
  color: #1f4b38;
}
@media (max-width: 420px) {
  .measure-grid {
    grid-template-columns: 1fr;
  }
}
.notes-warning {
  margin: 8px 0 0;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: #fbf2dc;
  color: #6b4a05;
}
.field {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}
.summary {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.line {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}
.line.total {
  margin-top: 6px;
  font-weight: 600;
  font-size: var(--step-1);
}
.ready {
  margin: 8px 0 0;
  color: var(--ok);
}
.range-error {
  font-size: 0.75rem;
  color: var(--danger);
}

</style>
