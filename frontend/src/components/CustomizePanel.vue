<script setup>
// "Make it yours": choose changes and see the price, which Flask calculates.
// Choosing "Made to your measurements" replaces S/M/L with the customer's own measurements.
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'
import { useSizeGuide } from '../stores/sizeGuide.js'
import { formatPriceChange, formatTaka, readyDate } from '../utils/format.js'

const props = defineProps({
  product: { type: Object, required: true },
})
const emit = defineEmits(['change', 'use-size'])
const route = useRoute()
const sizeGuide = useSizeGuide()

// Only the bust is needed for every piece; the server checks the same ranges (pricing.MEASUREMENTS)
const MEASUREMENTS = [
  { key: 'bust', label: 'Bust', required: true, min: 20, max: 72 },
  { key: 'waist', label: 'Waist', required: false, min: 20, max: 72 },
  { key: 'sleeve_length', label: 'Sleeve length', required: false, min: 4, max: 30 },
  { key: 'length', label: 'Length', required: false, min: 20, max: 72 },
]

// One choice per group; null means "as shown".
const choices = reactive(Object.fromEntries(props.product.customization.map((group) => [group.group, null])))
const measurements = reactive({ bust: '', waist: '', sleeve_length: '', length: '' })
const notes = ref('')
// A picture for the tailor: uploaded when chosen, because the bag can't hold a file
const picture = ref(null) // { name (from the server), filename, previewUrl }
const pictureInput = ref(null)
const uploadingPicture = ref(false)
const pictureError = ref('')
const quote = ref(null)
const error = ref('')

const allOptions = computed(() => props.product.customization.flatMap((group) =>
  group.options.map((option) => ({ ...option, group: group.group }))))
// The option that means "cut to my body", if the shop offers one
const measureOption = computed(() => allOptions.value.find((option) => option.needs_measurements) || null)
const madeToMeasure = computed(() => Boolean(measureOption.value) && choices[measureOption.value.group] === measureOption.value.id)
// A made-to-measure piece is cut to the exact length typed in, so the "2 inches shorter" options don't apply
const hiddenGroups = computed(() => (madeToMeasure.value
  ? props.product.customization.filter((group) => group.options.some((option) => option.new_length_inches)).map((group) => group.group)
  : []))

const optionIds = computed(() => Object.entries(choices)
  .filter(([group, id]) => id !== null && !hiddenGroups.value.includes(group))
  .map(([, id]) => id))

const cleanMeasurements = computed(() => Object.fromEntries(
  Object.entries(measurements).filter(([, value]) => value !== '' && value !== null).map(([key, value]) => [key, Number(value)])))
const measurementsComplete = computed(() => MEASUREMENTS.every(({ key, required, min, max }) => {
  const value = cleanMeasurements.value[key]
  return value === undefined ? !required : value >= min && value <= max
}))
const measurementsText = computed(() => MEASUREMENTS.filter(({ key }) => cleanMeasurements.value[key] !== undefined)
  .map(({ key, label }) => `${label.toLowerCase()} ${cleanMeasurements.value[key]} in`).join(', '))

// Smart check: if a standard size already fits these measurements, say so. It saves the customer the made-to-measure charge.
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
  const sameLength = (!length || length === props.product.length_inches) && !sleeve
  return { size: fits.size, close, sameLength }
})

let requestNumber = 0
async function refreshQuote() {
  const thisRequest = ++requestNumber
  error.value = ''
  try {
    const result = await api('/price-quote', {
      method: 'POST',
      body: { product_code: props.product.code, option_ids: optionIds.value },
    })
    if (thisRequest === requestNumber) quote.value = result // ignore answers to older requests
  } catch (err) {
    if (thisRequest === requestNumber) error.value = err.message
  }
}

watch(optionIds, refreshQuote, { immediate: true })
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

function pick(group, id) {
  choices[group] = choices[group] === id ? null : id
}

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
  if (picture.value) URL.revokeObjectURL(picture.value.previewUrl)
  picture.value = null
}

function useStandardSize(size) {
  choices[measureOption.value.group] = null
  emit('use-size', size)
}

// Arriving from the stylist chat: the changes the customer described are in the address,
// e.g. ?sleeves=Sleeveless&bust=38&length=36. Fill them in; the price is still worked out here.
function applyFromAddress() {
  const query = route.query
  const sleeves = allOptions.value.find((option) => option.label === query.sleeves)
  if (sleeves) choices[sleeves.group] = sleeves.id
  let anyMeasurement = false
  for (const { key } of MEASUREMENTS) {
    if (query[key]) {
      measurements[key] = Number(query[key]) || ''
      anyMeasurement = true
    }
  }
  if (anyMeasurement && measureOption.value) choices[measureOption.value.group] = measureOption.value.id
}
applyFromAddress()
</script>

<template>
  <section class="customize" aria-labelledby="customize-title">
    <h2 id="customize-title" class="title">Make it yours</h2>
    <p class="muted small">
      Change the sleeves, length, lining or fit. We make it to order and the price updates as you choose:
      changes that use less fabric cost less.
    </p>

    <template v-for="group in product.customization" :key="group.group">
      <fieldset v-if="!hiddenGroups.includes(group.group)" class="group">
        <legend>{{ group.group }} <span v-if="group.current" class="current">now: {{ group.current }}</span></legend>
        <div class="pills">
          <button
            type="button"
            class="pill"
            :aria-pressed="choices[group.group] === null"
            @click="choices[group.group] = null"
          >
            {{ group.options.some((option) => option.needs_measurements) ? 'Standard size' : 'As shown' }}
          </button>
          <button
            v-for="option in group.options"
            :key="option.id"
            type="button"
            class="pill"
            :aria-pressed="choices[group.group] === option.id"
            @click="pick(group.group, option.id)"
          >
            {{ option.label }}<template v-if="option.new_length_inches"> ({{ option.new_length_inches }} in)</template><template v-else-if="option.sleeve_length_inches"> (about {{ option.sleeve_length_inches }} in)</template>
            <span class="extra" :class="{ saving: option.extra_price_bdt < 0 }">{{ formatPriceChange(option.extra_price_bdt) }}</span>
          </button>
        </div>
      </fieldset>
    </template>

    <!-- Made to measure: the customer's own measurements take the place of S, M or L -->
    <fieldset v-if="madeToMeasure" class="group measure">
      <legend>Your measurements <span class="current">in inches</span></legend>
      <div class="measure-grid">
        <div v-for="item in MEASUREMENTS" :key="item.key">
          <label :for="`measure-${item.key}`">
            {{ item.label }} <span v-if="!item.required" class="muted">(optional)</span>
          </label>
          <input :id="`measure-${item.key}`" v-model="measurements[item.key]" type="number" inputmode="numeric"
            :min="item.min" :max="item.max" step="1" :required="item.required"
            :placeholder="item.key === 'length' && product.length_inches ? String(product.length_inches) : ''" />
        </div>
      </div>
      <p class="muted small hint">
        Measure your body, not a garment. Only the bust is needed; add the others if this piece needs them.
        Leave length empty to keep it as shown<span v-if="product.length_inches"> ({{ product.length_inches }} in)</span>.
        Sleeve length is from the shoulder seam to where the sleeve should end. No need to choose S, M or L.
      </p>

      <p v-if="standardSize?.size && standardSize.close && standardSize.sameLength" class="tip small" role="status">
        Good news: these measurements match our size <strong>{{ standardSize.size }}</strong>.
        <button type="button" class="text-button" @click="useStandardSize(standardSize.size)">
          Order size {{ standardSize.size }} and save {{ formatTaka(measureOption.extra_price_bdt) }}
        </button>,
        or keep made to measure for an exact fit.
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
          {{ uploadingPicture ? 'Uploading…' : 'A photo or sketch of the neckline, sleeve or detail you want. Only the shop can see it.' }}
        </p>
        <p v-if="pictureError" class="message error" role="alert">{{ pictureError }}</p>
      </div>

      <!-- The price comes only from the options chosen above, never from what is typed or attached here. -->
      <p v-if="(notes.trim() || picture) && !optionIds.length" class="notes-warning small" role="status">
        Your note or picture isn’t sent yet. They go with made-to-order pieces only, so choose a change above.
        <template v-if="measureOption">
          To have it cut to your measurements, choose
          <button type="button" class="text-button" @click="pick(measureOption.group, measureOption.id)">
            {{ measureOption.label }} ({{ formatPriceChange(measureOption.extra_price_bdt) }})
          </button>.
        </template>
        Without a change, you get the standard size at the listed price.
      </p>
    </div>

    <p v-if="error" class="message error">{{ error }}</p>
    <div v-else-if="quote" class="summary" aria-live="polite">
      <div class="line"><span>Dress</span><span>{{ formatTaka(quote.base_price_bdt) }}</span></div>
      <div v-for="extra in quote.extras" :key="extra.id" class="line">
        <span>{{ extra.label }}</span><span>{{ formatPriceChange(extra.extra_price_bdt) }}</span>
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
  margin-top: 32px;
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
  margin: 18px 0 0;
}
legend {
  font-weight: 600;
  margin-bottom: 8px;
  padding: 0;
}
.extra,
.current {
  color: var(--muted);
  font-weight: 400;
}
.extra {
  margin-left: 6px; /* keeps "+৳200" apart from the option's name */
}
.current {
  margin-left: 6px;
}
.extra.saving {
  color: var(--ok);
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.measure-grid label {
  font-size: var(--step--1);
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
@media (max-width: 520px) {
  .measure-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.notes-warning {
  margin: 8px 0 0;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: #fbf2dc;
  color: #6b4a05;
}
.pill[aria-pressed='true'] .extra {
  color: #e9dde0;
}
.field {
  margin-top: 20px;
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
</style>
