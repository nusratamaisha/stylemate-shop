<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProductCard from '../components/ProductCard.vue'
import { useShop } from '../stores/shop.js'

const shop = useShop()
const route = useRoute()
const router = useRouter()

// Filters live in the URL, so a filtered page can be shared or bookmarked.
const occasion = computed(() => route.query.occasion || '')
const category = computed(() => route.query.category || '')
const customizable = computed(() => route.query.customizable === '1')

const products = computed(() => shop.products.filter((product) =>
  (!occasion.value || product.occasions.includes(occasion.value)) &&
  (!category.value || product.category === category.value) &&
  (!customizable.value || product.customizable),
))

// The collection is shown in sections, in this order. The first name is the product's
// category in the CSV; the second is the heading customers see. A category not listed
// here still gets its own section at the end, under its own name.
const SECTIONS = [
  ['Dress', 'Dresses'],
  ['Top', 'Tops'],
  ['Bottoms', 'Pants and skirts'],
  ['Co-ord set', 'Sets'],
]
const sectionTitle = (name) => SECTIONS.find(([category]) => category === name)?.[1] || name

const sections = computed(() => {
  const known = SECTIONS.map(([name]) => name)
  const others = [...new Set(products.value.map((product) => product.category))].filter((name) => !known.includes(name))
  return [...known, ...others]
    .map((name) => ({ name, title: sectionTitle(name), products: products.value.filter((product) => product.category === name) }))
    .filter((section) => section.products.length)
})

function setFilter(key, value) {
  const query = { ...route.query, [key]: value || undefined }
  router.replace({ query })
}
</script>

<template>
  <div class="page">
    <h1 class="title">The collection</h1>

    <div class="filters">
      <div class="filter" role="group" aria-label="Occasion">
        <span class="filter-name">Occasion</span>
        <div class="pills">
          <button type="button" class="pill" :aria-pressed="!occasion" @click="setFilter('occasion', '')">All</button>
          <button
            v-for="name in shop.info?.occasions || []"
            :key="name"
            type="button"
            class="pill"
            :aria-pressed="occasion === name"
            @click="setFilter('occasion', name)"
          >
            {{ name }}
          </button>
        </div>
      </div>

      <div class="filter" role="group" aria-label="Type">
        <span class="filter-name">Type</span>
        <div class="pills">
          <button type="button" class="pill" :aria-pressed="!category" @click="setFilter('category', '')">All</button>
          <button
            v-for="name in shop.info?.categories || []"
            :key="name"
            type="button"
            class="pill"
            :aria-pressed="category === name"
            @click="setFilter('category', name)"
          >
            {{ sectionTitle(name) }}
          </button>
        </div>
      </div>

      <label class="check">
        <input type="checkbox" :checked="customizable" @change="setFilter('customizable', $event.target.checked ? '1' : '')" />
        Only pieces we can customize
      </label>
    </div>

    <p class="muted count">{{ products.length }} {{ products.length === 1 ? 'piece' : 'pieces' }}</p>

    <template v-if="products.length">
      <section v-for="section in sections" :key="section.name" class="section" :aria-labelledby="`section-${section.name}`">
        <h2 :id="`section-${section.name}`" class="section-title">{{ section.title }}</h2>
        <div class="grid">
          <ProductCard v-for="product in section.products" :key="product.code" :product="product" />
        </div>
      </section>
    </template>
    <div v-else-if="shop.loaded" class="empty">
      <p>Nothing matches these filters.</p>
      <button type="button" class="button secondary" @click="router.replace({ query: {} })">Clear filters</button>
    </div>
  </div>
</template>

<style scoped>
.section + .section {
  margin-top: 48px;
}
.section-title {
  font-size: var(--step-2);
  margin-bottom: 16px;
}
.title {
  padding-top: 40px;
}
.filters {
  display: grid;
  gap: 14px;
  padding: 20px 0;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.filter {
  display: grid;
  grid-template-columns: 90px 1fr;
  align-items: center;
  gap: 12px;
}
.filter-name {
  font-weight: 600;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
  margin: 0;
}
.check input {
  width: 18px;
  height: 18px;
}
.count {
  margin: 16px 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 36px 22px;
}
.empty {
  padding: 48px 0;
}
@media (max-width: 900px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 640px) {
  .filter {
    grid-template-columns: 1fr;
    gap: 6px;
  }
}
</style>
