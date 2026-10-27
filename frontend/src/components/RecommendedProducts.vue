<script setup>
// "You may also like" on a product page: pieces like productCode. Flask asks Gigalogy's
// recommender and keeps only pieces this customer can buy (services/recommendations.py); nothing shows if there are none.
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'
import ProductCard from './ProductCard.vue'
import { useAccount } from '../stores/account.js'
import { visitorId } from '../utils/visitor.js'

const props = defineProps({
  title: { type: String, required: true },
  productCode: { type: String, required: true },
})
const account = useAccount()
const products = ref([])

// Ask again when the piece changes, and on log in or out (a usual size changes the picks)
const ask = computed(() => [props.productCode, account.state.customer?.preferred_size])
watch(ask, async () => {
  try {
    const result = await api(`/products/${encodeURIComponent(props.productCode)}/recommendations?visitor_id=${encodeURIComponent(visitorId())}`)
    products.value = result.products
  } catch {
    products.value = [] // a suggestion row is a bonus: never show an error for it
  }
}, { immediate: true })
</script>

<template>
  <section v-if="products.length" class="recommended" :aria-label="title">
    <h2 class="title">{{ title }}</h2>
    <div class="grid">
      <ProductCard v-for="product in products" :key="product.code" :product="product" />
    </div>
  </section>
</template>

<style scoped>
.recommended {
  margin-top: 56px;
  padding-top: 32px;
  border-top: 1px solid var(--line);
}
.title {
  font-size: var(--step-2);
  margin-bottom: 20px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 36px 22px;
}
@media (max-width: 900px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
