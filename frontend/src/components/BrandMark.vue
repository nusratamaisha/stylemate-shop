<script setup>
// The shop's monogram: the M in its quotation marks, as in the name The House of "M".
defineProps({ size: { type: String, default: '1em' } })
</script>

<template>
  <span class="brand-mark" :style="{ fontSize: size }" aria-hidden="true">
    <span class="quote">“</span>M<span class="quote">”</span>
  </span>
</template>

<style scoped>
.brand-mark {
  font-family: var(--font-display);
  font-weight: 500;
  line-height: 1;
  color: var(--sindoor);
  letter-spacing: -0.04em;
  white-space: nowrap;
}
.quote {
  color: var(--haldi);
  font-weight: 400;
}
</style>
