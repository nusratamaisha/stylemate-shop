<script setup>
// "Make it yours": choose changes and see the price, which Flask calculates.
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../api.js'
import { formatTaka, readyDate } from '../utils/format.js'

const props = defineProps({
  product: { type: Object, required: true },
})
const emit = defineEmits(['change'])

// One choice per group; null means "as shown".
const choices = reactive(Object.fromEntries(props.product.customization.map((group) => [group.group, null])))
const notes = ref('')
const quote = ref(null)
const error = ref('')

const optionIds = computed(() => Object.values(choices).filter((id) => id !== null))

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
watch([quote, notes, optionIds], () => {
  emit('change', { quote: quote.value, optionIds: optionIds.value, notes: notes.value.trim() })
})

function pick(group, id) {
  choices[group] = choices[group] === id ? null : id
}
</script>

<template>
  <section class="customize" aria-labelledby="customize-title">
    <h2 id="customize-title" class="title">Make it yours</h2>
    <p class="muted small">Change the sleeves, length, lining or fit. We make it to order and the price updates as you choose.</p>

    <fieldset v-for="group in product.customization" :key="group.group" class="group">
      <legend>{{ group.group }} <span v-if="group.current" class="current">now: {{ group.current }}</span></legend>
      <div class="pills">
        <button
          type="button"
          class="pill"
          :aria-pressed="choices[group.group] === null"
          @click="choices[group.group] = null"
        >
          As shown
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
          <span class="extra">+{{ formatTaka(option.extra_price_bdt) }}</span>
        </button>
      </div>
    </fieldset>

    <div class="field">
      <label for="custom-notes">Measurements or notes <span class="muted">(optional)</span></label>
      <textarea id="custom-notes" v-model="notes" rows="2" maxlength="500"
        placeholder="For example: bust 34, waist 28, length 52 inches"></textarea>
    </div>

    <p v-if="error" class="message error">{{ error }}</p>
    <div v-else-if="quote" class="summary" aria-live="polite">
      <div class="line"><span>Dress</span><span>{{ formatTaka(quote.base_price_bdt) }}</span></div>
      <div v-for="extra in quote.extras" :key="extra.id" class="line">
        <span>{{ extra.label }}</span><span>+{{ formatTaka(extra.extra_price_bdt) }}</span>
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
