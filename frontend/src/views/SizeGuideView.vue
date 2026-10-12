<script setup>
import SizeGuide from '../components/SizeGuide.vue'
</script>

<template>
  <div class="page guide">
    <h1>Size guide</h1>
    <p class="muted">Find your size before you order. Every piece also lists its own length and sleeves on its page.</p>
    <SizeGuide />
  </div>
</template>

<style scoped>
.guide {
  max-width: 720px;
  padding-top: 40px;
}
h1 {
  margin-bottom: 4px;
}
</style>
