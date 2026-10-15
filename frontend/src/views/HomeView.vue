<script setup>
// The home page: one clear headline, the four sections as picture tiles, and the newest pieces.
// Kept short on purpose; the details live on the product pages and the Help page.
import { computed } from 'vue'
import BrandMark from '../components/BrandMark.vue'
import ProductCard from '../components/ProductCard.vue'
import ProductImage from '../components/ProductImage.vue'
import { useChat } from '../stores/chat.js'
import { useShop } from '../stores/shop.js'
import { SECTIONS } from '../utils/sections.js'

const shop = useShop()
const chat = useChat()
const featured = computed(() => shop.products.slice(0, 8))
// Photos for the hero and the tiles come from pieces not already in "New in", so no photo shows twice
const notFeatured = (product) => product.image_url && !featured.value.includes(product)
const heroPiece = computed(() => shop.products.filter((product) => product.category === 'Dress' && notFeatured(product)).at(-1))

// One tile per section that has pieces, showing that section's first photo
const tiles = computed(() => SECTIONS
  .map(([category, title]) => {
    const pieces = shop.products.filter((product) => product.category === category)
    return { category, title, count: pieces.length, cover: pieces.find(notFeatured) || pieces.find((product) => product.image_url) }
  })
  .filter((tile) => tile.count))
</script>

<template>
  <section class="hero">
    <div class="page hero-inner">
      <div class="hero-text">
        <h1>Clothes made to fit you.</h1>
        <p class="lead">Dresses, tops and sets. Change the fit, see it first, or ask our stylist.</p>
        <div class="actions">
          <RouterLink to="/shop" class="button">Shop now</RouterLink>
          <button type="button" class="button secondary" @click="chat.state.open = true">Ask our stylist</button>
        </div>
      </div>
      <div class="hero-art" aria-hidden="true">
        <ProductImage v-if="heroPiece" :product="heroPiece" class="hero-photo" />
        <BrandMark v-else size="clamp(7rem, 20vw, 12rem)" />
      </div>
    </div>
  </section>

  <section v-if="tiles.length" class="page block" aria-labelledby="sections-title">
    <h2 id="sections-title">Shop by section</h2>
    <div class="tiles">
      <RouterLink v-for="tile in tiles" :key="tile.category" :to="{ path: '/shop', query: { category: tile.category } }" class="tile">
        <ProductImage v-if="tile.cover" :product="tile.cover" class="tile-photo" />
        <span class="tile-label">{{ tile.title }} <span class="tile-count">{{ tile.count }}</span></span>
      </RouterLink>
    </div>
  </section>

  <section class="page block" aria-labelledby="new-title">
    <div class="section-head">
      <h2 id="new-title">New in</h2>
      <RouterLink to="/shop" class="see-all">See all →</RouterLink>
    </div>
    <div class="grid">
      <ProductCard v-for="product in featured" :key="product.code" :product="product" />
    </div>
  </section>

  <!-- The three things this shop does differently, in a word each; the product page explains them -->
  <section class="page block" aria-label="Why shop here">
    <ul class="features">
      <li><span class="feature-icon" aria-hidden="true">✂</span>Made to your size</li>
      <li><span class="feature-icon" aria-hidden="true">✦</span>See it before you buy</li>
      <li><span class="feature-icon" aria-hidden="true">💬</span>Ask by text or voice</li>
    </ul>
  </section>
</template>

<style scoped>
.hero {
  background: var(--sindoor-wash);
}
.hero-inner {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  align-items: center;
  gap: clamp(24px, 5vw, 64px);
  padding-top: clamp(32px, 5vw, 56px);
  padding-bottom: clamp(32px, 5vw, 56px);
}
.hero-text h1 {
  max-width: 12ch;
  font-size: clamp(2.25rem, 4.6vw, 3.5rem);
}
.lead {
  font-size: var(--step-1);
  color: var(--muted);
  max-width: 36ch;
  margin: 0;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}
.hero-art {
  display: grid;
  place-items: center;
}
.hero-photo {
  width: min(100%, 360px);
  box-shadow: var(--shadow);
}
.block {
  padding-top: clamp(40px, 6vw, 64px);
}
.block h2 {
  font-size: var(--step-3);
  margin-bottom: 20px;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
}
.tile {
  display: block;
  color: var(--kohl);
  text-decoration: none;
}
.tile-photo {
  transition: transform var(--ease), box-shadow var(--ease);
}
.tile:hover .tile-photo {
  transform: translateY(-3px);
  box-shadow: var(--shadow);
}
.tile-label {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 10px;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: var(--step-1);
}
.tile-count {
  font: 500 var(--step--1) / 1 var(--font-body);
  color: var(--muted);
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
}
.see-all {
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 32px 20px;
}
.features {
  list-style: none;
  margin: 0;
  padding: 24px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-around;
  gap: 16px 32px;
  border-radius: var(--radius-large);
  background: var(--jamdani);
  font-weight: 500;
}
.features li {
  display: flex;
  align-items: center;
  gap: 10px;
}
.feature-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #fff;
  color: var(--sindoor);
}
@media (max-width: 900px) {
  .tiles,
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 760px) {
  .hero-inner {
    grid-template-columns: 1fr;
  }
  .hero-art {
    display: none; /* on a phone the photos below say it better than one cropped picture */
  }
  .lead {
    font-size: var(--step-0);
  }
  .features {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
