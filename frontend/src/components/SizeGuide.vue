<script setup>
// The size guide tables. Used on its own page and in the pop-up on a product page.
import { computed } from 'vue'
import { useSizeGuide } from '../stores/sizeGuide.js'

const props = defineProps({
  onlySizes: { type: Array, default: null }, // a product's sizes; null shows every size
  selectedSize: { type: String, default: '' },
})

const guide = useSizeGuide()
const sizes = computed(() => {
  if (!props.onlySizes) return guide.sizes
  return guide.sizes.filter((row) => props.onlySizes.includes(row.size))
})
const cm = (inches) => Math.round(inches * 2.54)
</script>

<template>
  <div class="size-guide">
    <p v-if="guide.error" class="message error">{{ guide.error }}</p>
    <p v-else-if="!guide.loaded" class="muted">Loading the size guide…</p>

    <template v-else>
      <section v-if="sizes.length">
        <h3>Which size fits you</h3>
        <p class="muted small">Your body measurements, not the garment’s. Inches, with centimetres in brackets.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th scope="col">Size</th><th scope="col">Bust</th><th scope="col">Waist</th><th scope="col">Hip</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in sizes" :key="row.size" :class="{ selected: row.size === selectedSize }">
                <th scope="row">{{ row.size }}</th>
                <td>{{ row.bust_inches }} <span class="muted">({{ cm(row.bust_inches) }})</span></td>
                <td>{{ row.waist_inches }} <span class="muted">({{ cm(row.waist_inches) }})</span></td>
                <td>{{ row.hip_inches }} <span class="muted">({{ cm(row.hip_inches) }})</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="muted small">Between two sizes? Choose the larger one, or pick “Made to your measurements” on pieces that can be customized.</p>
      </section>
      <p v-else-if="onlySizes" class="muted">This piece uses its own sizes. Ask the stylist if you’re unsure.</p>

      <section v-if="guide.sleeves.length">
        <h3>How long each sleeve is</h3>
        <p class="muted small">From the shoulder seam to the edge of the sleeve.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th scope="col">Sleeve</th><th scope="col">Length</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in guide.sleeves" :key="row.name">
                <th scope="row">{{ row.name }}</th>
                <td>about {{ row.length_inches }} in <span class="muted">({{ cm(row.length_inches) }} cm)</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3>How to measure</h3>
        <ul class="small">
          <li><strong>Bust:</strong> around the fullest part of your chest, tape level.</li>
          <li><strong>Waist:</strong> around the narrowest part, usually just above the navel.</li>
          <li><strong>Hip:</strong> around the fullest part of your hips.</li>
          <li><strong>Length:</strong> each piece lists its own length, measured from the shoulder to the hem.</li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
section + section {
  margin-top: 28px;
}
h3 {
  font-size: var(--step-1);
  margin-bottom: 4px;
}
.table-wrap {
  overflow-x: auto;
  margin: 10px 0;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 9px 12px;
  text-align: left;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
thead th {
  font-weight: 600;
  background: var(--jamdani);
}
tbody th {
  font-weight: 600;
}
tr.selected {
  background: var(--sindoor-wash);
}
ul {
  margin: 8px 0 0;
  padding-left: 20px;
}
li + li {
  margin-top: 4px;
}
</style>
