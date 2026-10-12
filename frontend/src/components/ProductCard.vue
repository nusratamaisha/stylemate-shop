<script setup>
import ProductImage from './ProductImage.vue'
import { formatTaka } from '../utils/format.js'

defineProps({ product: { type: Object, required: true } })
</script>

<template>
  <RouterLink :to="`/products/${product.code}`" class="product-card">
    <div class="photo">
      <ProductImage :product="product" class="image" />
      <span v-if="!product.in_stock" class="badge out">Out of stock</span>
      <span v-if="product.customizable" class="badge custom">Can be customized</span>
    </div>
    <div class="info">
      <h3 class="name">{{ product.name }}</h3>
      <p class="price">{{ formatTaka(product.price_bdt) }}</p>
    </div>
  </RouterLink>
</template>

<style scoped>
.product-card {
  display: block;
  color: inherit;
  text-decoration: none;
}
.photo {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-large);
  transition: box-shadow var(--ease), transform var(--ease);
}
.image {
  border-radius: 0;
  transition: transform 500ms ease;
}
.product-card:hover .photo {
  box-shadow: var(--shadow);
  transform: translateY(-3px);
}
.product-card:hover .image {
  transform: scale(1.04);
}
/* Labels sit on the photo, so every card's name and price line up */
.badge {
  position: absolute;
  left: 10px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1;
  backdrop-filter: blur(6px);
}
.badge.custom {
  bottom: 10px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--sindoor-deep);
}
.badge.out {
  top: 10px;
  background: rgba(43, 32, 36, 0.78);
  color: #fff;
}
.info {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  padding: 12px 2px 0;
}
.name {
  font-family: var(--font-body);
  font-weight: 500;
  font-size: var(--step-0);
  line-height: 1.35;
  margin: 0;
}
.product-card:hover .name {
  color: var(--sindoor);
}
.price {
  margin: 0;
  font-weight: 600;
  white-space: nowrap;
}
</style>
