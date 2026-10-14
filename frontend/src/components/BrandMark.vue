<script setup>
// The shop's logo: a clothes hanger (the closet) with a gold bracket in the corner (the corner).
// Drawn as SVG so it stays sharp at any size. The same drawing is the browser tab icon (public/favicon.svg).
defineProps({ size: { type: String, default: '1em' } })
</script>

<template>
  <svg class="brand-mark" :style="{ fontSize: size }" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
    <rect class="tile" width="64" height="64" rx="14" />
    <g fill="none" stroke-linecap="round" stroke-linejoin="round">
      <path class="hanger" d="M27.4 13.2a4.6 4.6 0 1 1 6.6 4.1c-1.3.6-2 1.4-2 2.7v1" />
      <path class="hanger" d="M32 21 14.6 32.3c-2 1.3-1.1 4.4 1.3 4.4h32.2c2.4 0 3.3-3.1 1.3-4.4Z" />
      <path class="corner" d="M42 54h12V42" />
    </g>
  </svg>
</template>

<style scoped>
.brand-mark {
  display: block;
  flex: none;
  width: 1em;
  height: 1em;
}
.tile {
  fill: var(--sindoor);
}
.hanger {
  stroke: #fff;
  stroke-width: 3;
}
.corner {
  stroke: var(--haldi);
  stroke-width: 3.5;
}
</style>
