<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'
import CustomizePanel from '../components/CustomizePanel.vue'
import PreviewPanel from '../components/PreviewPanel.vue'
import ProductReviews from '../components/ProductReviews.vue'
import RecommendedProducts from '../components/RecommendedProducts.vue'
import ProductImage from '../components/ProductImage.vue'
import SizeGuide from '../components/SizeGuide.vue'
import { useAccount } from '../stores/account.js'
import { useBag } from '../stores/bag.js'
import { useChat } from '../stores/chat.js'
import { isLight, swatch } from '../utils/colours.js'
import { formatTaka } from '../utils/format.js'

const props = defineProps({ code: { type: String, required: true } })
const bag = useBag()
const chat = useChat()
const account = useAccount()

const product = ref(null)
const loadError = ref('')
const colour = ref('')
const size = ref('')
const custom = ref({ quote: null, optionIds: [], notes: '', referenceImage: '', madeToMeasure: false, measurements: null, measurementsComplete: true, measurementsText: '' })
const added = ref(false)
const sizeGuideDialog = ref(null)
const sizeGuideOpened = ref(false) // load the guide only when someone asks for it

async function load() {
  product.value = null
  loadError.value = ''
  try {
    product.value = await api(`/products/${encodeURIComponent(props.code)}`)
    colour.value = product.value.colours[0] || ''
    size.value = usualSize.value // '' unless the customer's usual size is one this piece comes in
    custom.value = { quote: null, optionIds: [], notes: '', referenceImage: '', madeToMeasure: false, measurements: null, measurementsComplete: true, measurementsText: '' }
  } catch (error) {
    loadError.value = error.message
  }
}
watch(() => props.code, load, { immediate: true })

// A returning customer's usual size (saved from their last order) is chosen for them, if this piece comes in it
const usualSize = computed(() => {
  const saved = account.state.customer?.preferred_size
  return saved && product.value?.sizes.includes(saved) ? saved : ''
})
watch(usualSize, (saved) => {
  if (saved && !size.value) size.value = saved
}, { immediate: true })

// Typing any measurement makes it made to measure at once, before Flask's price arrives
const madeToMeasure = computed(() => custom.value.madeToMeasure)
const isCustom = computed(() => custom.value.optionIds.length > 0 || madeToMeasure.value)
const price = computed(() => (isCustom.value && custom.value.quote ? custom.value.quote.total_bdt : product.value?.price_bdt))
const stockText = computed(() => {
  const stock = product.value?.stock ?? 0
  if (stock === 0) return product.value?.customizable ? 'Out of stock ready-made. Add your measurements below and we’ll make one for you.' : 'Out of stock'
  if (stock <= 5) return `Only ${stock} left`
  return 'In stock'
})
const canAdd = computed(() => {
  if (!product.value || !colour.value) return false
  if (madeToMeasure.value) return Boolean(custom.value.quote) && custom.value.measurementsComplete
  if (!size.value) return false
  if (isCustom.value) return Boolean(custom.value.quote)
  return product.value.in_stock
})
const buttonText = computed(() => {
  if (madeToMeasure.value && !custom.value.measurementsComplete) return 'Enter your measurements'
  if (!madeToMeasure.value && !size.value) return 'Choose a size'
  if (!isCustom.value && !product.value?.in_stock) return 'Out of stock'
  return isCustom.value ? `Add custom piece to bag (${formatTaka(price.value)})` : 'Add to bag'
})

function addToBag() {
  if (!canAdd.value) return
  bag.add({
    product_code: product.value.code,
    name: product.value.name,
    image_url: product.value.image_url,
    colours: product.value.colours,
    size: madeToMeasure.value ? 'Made to measure' : size.value,
    colour: colour.value,
    quantity: 1,
    option_ids: custom.value.optionIds,
    measurements: madeToMeasure.value ? custom.value.measurements : null,
    // Shown in the bag. The server writes its own copy when the order is placed.
    custom_details: isCustom.value
      ? [custom.value.quote.details, madeToMeasure.value ? `Measurements: ${custom.value.measurementsText}` : ''].filter(Boolean).join('; ')
      : '',
    notes: isCustom.value ? custom.value.notes : '',
    reference_image: isCustom.value ? custom.value.referenceImage : '',
    unit_price_bdt: price.value,
  })
  added.value = true
  setTimeout(() => (added.value = false), 4000)
}

function openSizeGuide() {
  sizeGuideOpened.value = true
  sizeGuideDialog.value.showModal()
}

function askAbout() {
  chat.state.open = true
  chat.ask(`Tell me more about the ${product.value.name}. What would I wear it with?`)
}
</script>

<template>
  <div class="page">
    <p v-if="loadError" class="message error">{{ loadError }} <RouterLink to="/shop">Back to the collection</RouterLink></p>

    <article v-else-if="product" class="product">
      <ProductImage :product="product" :colour="colour" class="image" />

      <div class="details">
        <p class="crumbs small"><RouterLink to="/shop">The collection</RouterLink> / {{ product.category }}</p>
        <h1 class="name">{{ product.name }}</h1>
        <p class="price">{{ formatTaka(price) }}</p>
        <p class="description">{{ product.description }}</p>

        <dl class="facts">
          <div><dt>Fabric</dt><dd>{{ product.fabric }}</dd></div>
          <div v-if="product.length_inches"><dt>Length</dt><dd>{{ product.length_inches }} inches, shoulder to hem</dd></div>
          <div v-if="product.sleeve"><dt>Sleeves</dt><dd>{{ product.sleeve }}</dd></div>
          <div v-if="product.occasions.length"><dt>Wear it for</dt><dd>{{ product.occasions.join(', ') }}</dd></div>
        </dl>

        <fieldset class="choice">
          <legend>Colour: <span class="muted">{{ colour }}</span></legend>
          <div class="colours">
            <button
              v-for="name in product.colours"
              :key="name"
              type="button"
              class="colour"
              :class="{ light: isLight(name) }"
              :style="{ background: swatch(name) }"
              :aria-pressed="colour === name"
              :aria-label="name"
              :title="name"
              @click="colour = name"
            ></button>
          </div>
        </fieldset>

        <p v-if="madeToMeasure" class="measured-note">
          <strong>Size:</strong> made to your measurements. No need to choose S, M or L.
        </p>
        <fieldset v-else class="choice">
          <legend>
            Size
            <button type="button" class="text-button guide-link" @click="openSizeGuide">Size guide</button>
          </legend>
          <div class="pills">
            <button
              v-for="name in product.sizes"
              :key="name"
              type="button"
              class="pill"
              :aria-pressed="size === name"
              @click="size = name"
            >
              {{ name }}
            </button>
          </div>
          <p v-if="usualSize && size === usualSize" class="usual small">{{ usualSize }} is your usual size.</p>
        </fieldset>

        <p class="stock" :class="{ out: !product.in_stock }">{{ stockText }}</p>

        <CustomizePanel v-if="product.customizable" :key="product.code + JSON.stringify($route.query)" :product="product" @change="custom = $event" @use-size="size = $event" />
        <PreviewPanel v-if="product.preview_available" :product="product" :colour="colour" :option-ids="custom.optionIds"
          :size="size" :made-to-measure="madeToMeasure" :measurements="custom.measurements" />

        <div class="buy">
          <button type="button" class="button" :disabled="!canAdd" @click="addToBag">{{ buttonText }}</button>
          <p v-if="added" class="message ok" role="status">Added to your bag. <RouterLink to="/bag">View bag</RouterLink></p>
          <button type="button" class="text-button" @click="askAbout">Ask the stylist about this piece</button>
        </div>
      </div>
    </article>

    <RecommendedProducts v-if="product" title="You may also like" :product-code="product.code" />
    <ProductReviews v-if="product" :code="product.code" />

    <dialog ref="sizeGuideDialog" class="size-dialog" aria-labelledby="size-dialog-title" @click.self="sizeGuideDialog.close()">
      <div class="size-dialog-body">
        <div class="size-dialog-head">
          <h2 id="size-dialog-title">Size guide</h2>
          <button type="button" class="text-button" @click="sizeGuideDialog.close()">Close</button>
        </div>
        <p v-if="product && (product.length_inches || product.sleeve)" class="small">
          This piece<span v-if="product.length_inches"> is {{ product.length_inches }} inches long, shoulder to hem</span><span v-if="product.length_inches && product.sleeve">, and</span><span v-if="product.sleeve"> has {{ product.sleeve.toLowerCase() }} sleeves</span>.
        </p>
        <SizeGuide v-if="sizeGuideOpened && product" :only-sizes="product.sizes" :selected-size="size" />
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.product {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: clamp(24px, 5vw, 64px);
  padding-top: 40px;
  align-items: start;
}
.image {
  position: sticky;
  top: 92px;
}
.crumbs {
  margin-bottom: 8px;
  color: var(--muted);
}
.name {
  font-size: clamp(2rem, 4vw, 2.75rem);
  margin-bottom: 4px;
}
.price {
  font-size: var(--step-2);
  font-family: var(--font-display);
  margin-bottom: 16px;
}
.description {
  font-size: 1.0625rem;
}
.facts {
  display: grid;
  gap: 4px;
  margin: 0 0 24px;
}
.facts div {
  display: flex;
  gap: 8px;
}
.facts dt {
  font-weight: 600;
}
.facts dd {
  margin: 0;
}
.choice {
  border: 0;
  padding: 0;
  margin: 0 0 20px;
}
legend {
  font-weight: 600;
  margin-bottom: 10px;
  padding: 0;
}
.measured-note {
  padding: 10px 14px;
  border-radius: var(--radius);
  background: var(--jamdani);
}
.guide-link {
  margin-left: 12px;
  font-weight: 400;
}
.size-dialog {
  width: min(640px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  padding: 0;
  border: 0;
  border-radius: 10px;
  color: var(--kohl);
}
.size-dialog::backdrop {
  background: rgba(43, 32, 36, 0.45);
}
.size-dialog-body {
  padding: 24px;
}
.size-dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 8px;
}
.size-dialog-head h2 {
  font-size: var(--step-2);
  margin: 0;
}
.colours {
  display: flex;
  gap: 12px;
}
.colour {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px var(--line);
  cursor: pointer;
}
.colour.light {
  box-shadow: 0 0 0 1px #cbbfbb;
}
.colour[aria-pressed='true'] {
  box-shadow: 0 0 0 2px var(--kohl);
}
.stock {
  font-weight: 500;
  color: var(--ok);
}
.stock.out {
  color: var(--danger);
}
.buy {
  display: grid;
  gap: 12px;
  justify-items: start;
  margin-top: 28px;
}
@media (max-width: 800px) {
  .product {
    grid-template-columns: 1fr;
  }
  .image {
    position: static;
    max-width: 420px;
  }
}
.usual {
  margin: 6px 0 0;
  color: var(--muted);
}
</style>
