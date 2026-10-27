<script setup>
// "Shop" in the header, with a menu that opens on hover (or keyboard focus): the sections as
// photo tiles with how many pieces each has, the occasions, and made to measure. Every link
// goes to the shop page with its filter (ShopView reads ?category=, ?occasion=, ?customizable=).
// On touch screens there is no hover, so tapping "Shop" simply opens the shop page.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useShop } from '../stores/shop.js'
import { SECTIONS, sectionTitle } from '../utils/sections.js'

const shop = useShop()
const route = useRoute()
const open = ref(false)
let closeTimer = null

// Each section with a photo of its first piece that has one, so the menu shows what's inside.
// Same order as the shop page (utils/sections.js); a category not listed there comes last.
const order = (name) => { const at = SECTIONS.findIndex(([category]) => category === name); return at === -1 ? SECTIONS.length : at }
const sections = computed(() => [...(shop.info?.categories || [])].sort((a, b) => order(a) - order(b)).map((name) => {
  const pieces = shop.products.filter((product) => product.category === name)
  return { name, title: sectionTitle(name), count: pieces.length, photo: pieces.find((product) => product.image_url)?.image_url }
}).filter((section) => section.count))
const occasions = computed(() => shop.info?.occasions || [])
const customizableCount = computed(() => shop.products.filter((product) => product.customizable).length)

// Only a mouse opens it: a finger's tap should simply follow the link to the shop page
function show(event) {
  if (event.pointerType !== 'mouse') return
  clearTimeout(closeTimer)
  open.value = true
}
// A short pause, so moving the mouse from "Shop" down into the menu doesn't close it
function hideSoon(event) {
  if (event.pointerType !== 'mouse') return
  clearTimeout(closeTimer)
  closeTimer = setTimeout(() => (open.value = false), 150)
}
function onFocusOut(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) open.value = false
}
// Close once a link has been followed
watch(() => route.fullPath, () => (open.value = false))
</script>

<template>
  <div class="shop-menu" @pointerenter="show" @pointerleave="hideSoon" @focusin="open = true" @focusout="onFocusOut"
    @keydown.esc="open = false">
    <RouterLink to="/shop" :aria-expanded="open" aria-haspopup="true">
      Shop <span class="caret" aria-hidden="true">▾</span>
    </RouterLink>

    <div v-show="open" class="panel" role="region" aria-label="Shop by section">
      <div class="types">
        <p class="label">Shop by section</p>
        <div class="tiles">
          <RouterLink v-for="section in sections" :key="section.name" :to="{ path: '/shop', query: { category: section.name } }" class="tile">
            <span class="photo">
              <img v-if="section.photo" :src="section.photo" alt="" loading="lazy" />
            </span>
            <span class="tile-name">{{ section.title }}</span>
            <span class="tile-count">{{ section.count }} {{ section.count === 1 ? 'piece' : 'pieces' }}</span>
          </RouterLink>
        </div>
        <RouterLink to="/shop" class="all">See everything ({{ shop.products.length }}) →</RouterLink>
      </div>

      <div class="side">
        <div v-if="occasions.length">
          <p class="label">Shop by occasion</p>
          <ul>
            <li v-for="name in occasions" :key="name">
              <RouterLink :to="{ path: '/shop', query: { occasion: name } }">{{ name }}</RouterLink>
            </li>
          </ul>
        </div>
        <RouterLink v-if="customizableCount" :to="{ path: '/shop', query: { customizable: '1' } }" class="made">
          <strong>Made to measure</strong>
          <span>{{ customizableCount }} pieces we can sew to your size</span>
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shop-menu {
  position: relative;
}
/* The same look as the header's other links (App.vue's styles don't reach inside this component) */
.shop-menu > a {
  color: var(--kohl);
  text-decoration: none;
  font-weight: 500;
}
.shop-menu > a:hover,
.shop-menu > a.router-link-active,
.shop-menu > a[aria-expanded='true'] {
  color: var(--sindoor);
}
.caret {
  font-size: 0.7em;
  margin-left: 2px;
}
.panel {
  position: absolute;
  top: calc(100% + 18px);
  left: 50%;
  transform: translateX(-30%);
  z-index: 40;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 28px;
  width: min(760px, calc(100vw - 32px));
  padding: 22px 24px;
  border: 1px solid var(--line);
  border-radius: var(--radius-large);
  background: #fff;
  box-shadow: 0 18px 40px rgba(43, 32, 36, 0.12);
}
/* An invisible bridge over the gap, so the mouse can travel from "Shop" into the menu */
.panel::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: -20px;
  height: 20px;
}
.label {
  margin: 0 0 10px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}
.shop-menu .tile {
  display: grid;
  gap: 2px;
  align-content: start;
  color: var(--kohl);
  text-decoration: none;
}
.photo {
  display: block;
  aspect-ratio: 3 / 4;
  margin-bottom: 6px;
  overflow: hidden;
  border-radius: 10px;
  background: var(--jamdani);
}
.photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}
.tile:hover .photo img {
  transform: scale(1.04);
}
.tile-name {
  font-weight: 600;
}
.tile:hover .tile-name {
  color: var(--sindoor);
}
.tile-count {
  font-size: var(--step--1);
  font-weight: 400;
  color: var(--muted);
}
.shop-menu .all {
  display: inline-block;
  margin-top: 14px;
  font-size: var(--step--1);
}
.side {
  display: grid;
  gap: 18px;
  align-content: start;
  padding-left: 24px;
  border-left: 1px solid var(--line);
}
.side ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}
.side ul a {
  color: var(--kohl);
  text-decoration: none;
}
.side ul a:hover {
  color: var(--sindoor);
}
.shop-menu .made {
  display: grid;
  gap: 2px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--jamdani);
  color: var(--kohl);
  text-decoration: none;
}
.made span {
  font-size: var(--step--1);
  font-weight: 400;
  color: var(--muted);
}
.shop-menu .made:hover strong {
  color: var(--sindoor);
}
@media (prefers-reduced-motion: reduce) {
  .photo img {
    transition: none;
  }
}
</style>
