<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import BrandMark from './components/BrandMark.vue'
import ChatWidget from './components/ChatWidget.vue'
import { useAccount } from './stores/account.js'
import { useBag } from './stores/bag.js'
import { useShop } from './stores/shop.js'

const shop = useShop()
// The name comes from the shop's row in the database, so another shop needs no code change.
const shopName = computed(() => shop.info?.name || 'Closet Corner')
const bag = useBag()
const account = useAccount()
const route = useRoute()
const isOwnerPage = computed(() => route.path.startsWith('/owner'))
// Shown as typed, but with a capital first letter ("maisha" reads better as "Maisha")
const firstName = computed(() => {
  const name = (account.state.customer?.name || '').trim().split(/\s+/)[0]
  return name.charAt(0).toUpperCase() + name.slice(1)
})
</script>

<template>
  <a class="skip" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="page bar">
      <RouterLink to="/" class="brand" :aria-label="`${shopName}, home`">
        <BrandMark size="2.25rem" />
        <span class="brand-name">{{ shopName }}</span>
      </RouterLink>
      <!-- The store's pages in the middle; the customer's own things (account, bag) apart on the right. -->
      <nav v-if="!isOwnerPage" class="nav store" aria-label="Main">
        <RouterLink to="/shop">Shop</RouterLink>
        <RouterLink to="/size-guide">Size guide</RouterLink>
        <RouterLink to="/help">Help</RouterLink>
      </nav>
      <div v-if="!isOwnerPage" class="personal">
        <RouterLink to="/account" class="account-link" :aria-label="account.state.customer ? 'Your account' : 'Log in or create an account'">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-4 3.6-6 8-6s8 2 8 6" />
          </svg>
          <span>{{ account.state.customer ? firstName : 'Log in' }}</span>
        </RouterLink>
        <RouterLink to="/bag" class="bag-link">
          Bag <span v-if="bag.count.value" class="count">{{ bag.count.value }}</span>
        </RouterLink>
      </div>
      <nav v-else class="nav" aria-label="Owner">
        <RouterLink to="/">View shop</RouterLink>
      </nav>
    </div>
  </header>

  <main id="main">
    <p v-if="shop.error" class="page message error">{{ shop.error }}</p>
    <RouterView />
  </main>

  <footer class="site-footer">
    <div class="page foot" :class="{ 'with-chat': !isOwnerPage }">
      <p>
        <strong>{{ shopName }}</strong><br />
        Everyday elegance, made to fit you. Delivery across Bangladesh.
      </p>
      <p v-if="!isOwnerPage" class="small muted">
        Our stylist answers only from this shop’s catalogue, so it won’t guess.<br />
        <RouterLink to="/help">FAQ and contact</RouterLink> · <RouterLink to="/size-guide">Size guide</RouterLink>
      </p>
    </div>
  </footer>

  <ChatWidget v-if="!isOwnerPage" />
</template>

<style scoped>
.skip {
  position: absolute;
  left: -999px;
}
.skip:focus {
  left: 16px;
  top: 16px;
  z-index: 50;
  background: #fff;
  padding: 8px 12px;
}
.site-header {
  border-bottom: 1px solid var(--line);
  background: rgba(253, 251, 249, 0.88);
  backdrop-filter: blur(10px);
  position: sticky;
  top: 0;
  z-index: 30;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 68px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--kohl);
  text-decoration: none;
}
.brand-name {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
}
.nav {
  display: flex;
  gap: 24px;
  align-items: center;
}
.nav a {
  color: var(--kohl);
  text-decoration: none;
  font-weight: 500;
}
.nav a:hover,
.nav a.router-link-active {
  color: var(--sindoor);
}
.store {
  margin: 0 auto; /* centred between the brand and the personal links */
  padding: 0 24px;
}
.personal {
  display: flex;
  align-items: center;
  gap: 18px;
  padding-left: 24px;
  border-left: 1px solid var(--line);
}
.personal a {
  color: var(--kohl);
  text-decoration: none;
  font-weight: 500;
}
.personal a:hover,
.personal a.router-link-active {
  color: var(--sindoor);
}
.account-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
}
.account-link:hover,
.account-link.router-link-active {
  border-color: var(--sindoor);
  background: var(--sindoor-wash);
}
.icon {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
}
.count {
  display: inline-grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  margin-left: 4px;
  border-radius: 999px;
  background: var(--sindoor);
  color: #fff;
  font-size: 0.75rem;
}
main {
  min-height: 70vh;
  padding-bottom: 72px;
}
.site-footer {
  background: var(--kohl);
  color: #e9dfe1;
}
.site-footer strong {
  font-family: var(--font-display);
  font-size: var(--step-1);
  font-weight: 500;
  color: #fff;
}
.site-footer .muted {
  color: #b9aab0;
}
.site-footer a {
  color: #fff;
}
.site-footer a:hover {
  color: var(--haldi);
}
.foot {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
  padding-top: 32px;
  padding-bottom: 32px;
}
.foot.with-chat {
  padding-bottom: 96px; /* room for the chat button */
}
@media (max-width: 760px) {
  .store {
    gap: 14px;
    padding: 0 12px;
  }
  .personal {
    gap: 12px;
    padding-left: 12px;
  }
  .account-link span {
    display: none; /* the icon alone on small screens */
  }
  .account-link {
    padding: 0 8px;
  }
}
@media (max-width: 520px) {
  .brand-name {
    display: none;
  }
}
</style>
