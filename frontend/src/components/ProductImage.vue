<script setup>
// Shows the product photo. Until a photo is added (or if it fails to load),
// shows fabric swatches in the product's colours instead of a broken image.
import { computed, ref, watch } from 'vue'
import { swatch } from '../utils/colours.js'

const props = defineProps({
  product: { type: Object, required: true },
  colour: { type: String, default: '' }, // the colour the customer picked, shown first
})

const failed = ref(false)
watch(() => props.product.image_url, () => (failed.value = false))

const colours = computed(() => {
  const list = props.product.colours || []
  if (!props.colour) return list
  return [props.colour, ...list.filter((name) => name !== props.colour)]
})
</script>

<template>
  <div class="product-image">
    <img
      v-if="product.image_url && !failed"
      :src="product.image_url"
      :alt="product.name"
      loading="lazy"
      @error="failed = true"
    />
    <div v-else class="swatches" role="img" :aria-label="`${product.name} in ${colours.join(' or ')}`">
      <span
        v-for="(name, index) in colours"
        :key="name"
        class="swatch"
        :class="{ main: index === 0 }"
        :style="{ background: swatch(name) }"
      ></span>
      <span class="weave" aria-hidden="true"></span>
    </div>
  </div>
</template>

<style scoped>
.product-image {
  position: relative;
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background: var(--jamdani);
  border-radius: var(--radius-large);
}
img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.swatches {
  display: flex;
  height: 100%;
}
.swatch {
  flex: 1;
}
.swatch.main {
  flex: 3;
}
/* A faint woven texture so the swatch reads as fabric, not a flat block of colour. */
.weave {
  position: absolute;
  inset: 0;
  background-image:
    repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.07) 0 1px, transparent 1px 4px),
    repeating-linear-gradient(90deg, rgba(0, 0, 0, 0.05) 0 1px, transparent 1px 4px);
}
</style>
