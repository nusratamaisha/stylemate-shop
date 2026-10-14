<script setup>
import { computed } from 'vue'
import BrandMark from '../components/BrandMark.vue'
import ProductCard from '../components/ProductCard.vue'
import ProductImage from '../components/ProductImage.vue'
import { useChat } from '../stores/chat.js'
import { useShop } from '../stores/shop.js'

const shop = useShop()
const chat = useChat()
const featured = computed(() => shop.products.slice(0, 8))
// The hero shows the first and last dress that have a photo
const heroPieces = computed(() => {
  const dresses = shop.products.filter((product) => product.category === 'Dress' && product.image_url)
  return dresses.length > 1 ? [dresses[0], dresses[dresses.length - 1]] : dresses
})
</script>

<template>
  <section class="hero">
    <div class="page hero-inner">
      <div class="hero-text">
        <span class="eyebrow">{{ shop.info?.name || 'Closet Corner' }}</span>
        <h1>{{ shop.info?.tagline || 'Everyday elegance, made to fit you.' }}</h1>
        <p class="lead">
          Flowing maxis, easy tunics and everyday skirts, made to fit you.
          Not sure what suits the occasion? Ask our stylist by typing or speaking.
          It answers from our catalogue, so it never guesses.
        </p>
        <div class="actions">
          <RouterLink to="/shop" class="button">Shop the collection</RouterLink>
          <button type="button" class="button secondary" @click="chat.state.open = true">Ask our stylist</button>
        </div>
      </div>

      <!-- Two pieces from the collection. Until photos load, the monogram holds the space. -->
      <div class="hero-art" aria-hidden="true">
        <template v-if="heroPieces.length">
          <ProductImage :product="heroPieces[0]" class="hero-photo main" />
          <ProductImage v-if="heroPieces[1]" :product="heroPieces[1]" class="hero-photo second" />
        </template>
        <BrandMark v-else class="monogram" size="clamp(7rem, 20vw, 14rem)" />
      </div>
    </div>
  </section>

  <section class="page promises" aria-label="Why shop here">
    <div class="promise">
      <span class="promise-icon" aria-hidden="true">✂</span>
      <div>
        <h3>Made to fit you</h3>
        <p>Change the sleeves, length, lining or fit, and see the price as you choose.</p>
      </div>
    </div>
    <div class="promise">
      <span class="promise-icon" aria-hidden="true">✦</span>
      <div>
        <h3>See it first</h3>
        <p>Get a picture of a piece with your changes, or on you, before you order.</p>
      </div>
    </div>
    <div class="promise">
      <span class="promise-icon" aria-hidden="true">❝</span>
      <div>
        <h3>A stylist that doesn’t guess</h3>
        <p>Ask by text or voice. Answers come only from this shop’s catalogue.</p>
      </div>
    </div>
  </section>

  <section v-if="shop.info?.occasions?.length" class="page occasions">
    <span class="eyebrow">Find your piece</span>
    <h2>Shop by occasion</h2>
    <div class="pills">
      <RouterLink
        v-for="occasion in shop.info.occasions"
        :key="occasion"
        :to="{ path: '/shop', query: { occasion } }"
        class="pill occasion"
      >
        {{ occasion }}
      </RouterLink>
    </div>
  </section>

  <section class="page">
    <div class="section-head">
      <div>
        <span class="eyebrow">New in</span>
        <h2>This season’s pieces</h2>
      </div>
      <RouterLink to="/shop" class="see-all">See all {{ shop.products.length }} pieces →</RouterLink>
    </div>
    <div class="grid">
      <ProductCard v-for="product in featured" :key="product.code" :product="product" />
    </div>
  </section>

  <section class="page">
    <div class="made-to-fit">
      <div class="fit-text">
        <span class="eyebrow">Made to order</span>
        <h2>Made to fit you</h2>
        <p>
          Shorter or longer, different sleeves, an added lining, or cut to your measurements.
          Choose the changes on any piece marked “Can be customized” and see the price straight away.
          We make it to order in about a week.
        </p>
        <RouterLink :to="{ path: '/shop', query: { customizable: '1' } }" class="button">
          See pieces we can customize
        </RouterLink>
      </div>
      <BrandMark class="fit-mark" size="clamp(6rem, 16vw, 11rem)" />
    </div>
  </section>
</template>

<style scoped>
.hero {
  background: linear-gradient(180deg, var(--sindoor-wash) 0%, var(--paper) 100%);
}
.hero-inner {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  align-items: center;
  gap: clamp(24px, 5vw, 72px);
  padding-top: clamp(32px, 6vw, 72px);
  padding-bottom: clamp(40px, 7vw, 88px);
}
.hero-text h1 {
  max-width: 13ch;
  font-size: clamp(2.5rem, 5.2vw, 4rem);
}
.lead {
  font-size: var(--step-1);
  color: var(--muted);
  max-width: 44ch;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}
.hero-art {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 320px;
  padding: 0 6% 9% 12%;
}
/* An arched frame for the main photo, like a doorway into the house */
.hero-photo.main {
  width: 100%;
  border-radius: 999px 999px var(--radius-large) var(--radius-large);
  box-shadow: var(--shadow);
}
.hero-photo.second {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 38%;
  border: 6px solid var(--paper);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow);
}
.promises {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  padding-top: 40px;
  padding-bottom: 8px;
}
.promise {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.promise-icon {
  flex: none;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--sindoor-wash);
  color: var(--sindoor);
  font-size: 1.15rem;
}
.promise h3 {
  margin-bottom: 2px;
}
.promise p {
  margin: 0;
  color: var(--muted);
  font-size: var(--step--1);
}
.occasions {
  padding-top: 56px;
}
.occasion {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  font-size: var(--step-0);
  min-height: 46px;
  padding: 0 20px;
}
.occasion:hover {
  background: var(--kohl);
  border-color: var(--kohl);
  color: #fff;
}
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding-top: 64px;
  margin-bottom: 8px;
}
.see-all {
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
  padding-bottom: 14px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 36px 22px;
}
.made-to-fit {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  margin-top: 80px;
  padding: clamp(28px, 5vw, 56px);
  border-radius: var(--radius-large);
  background: var(--sindoor-wash);
  overflow: hidden;
}
.fit-text p {
  font-size: var(--step-1);
  max-width: 52ch;
  margin-bottom: 24px;
}
.fit-mark {
  flex: none;
  opacity: 0.9;
}
@media (max-width: 900px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .promises {
    grid-template-columns: 1fr;
    gap: 18px;
  }
  .fit-mark {
    display: none;
  }
}
@media (max-width: 760px) {
  .hero-inner {
    grid-template-columns: 1fr;
  }
  .hero-art {
    max-width: 420px;
    margin: 0 auto;
  }
  .lead {
    font-size: var(--step-0);
  }
}
</style>
