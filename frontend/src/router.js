import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import ShopView from './views/ShopView.vue'
import ProductView from './views/ProductView.vue'
import BagView from './views/BagView.vue'
import SizeGuideView from './views/SizeGuideView.vue'
import HelpView from './views/HelpView.vue'
import AccountView from './views/AccountView.vue'
import OwnerLoginView from './views/OwnerLoginView.vue'
import OwnerDashboardView from './views/OwnerDashboardView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/shop', component: ShopView },
    { path: '/products/:code', component: ProductView, props: true },
    { path: '/bag', component: BagView },
    { path: '/size-guide', component: SizeGuideView },
    { path: '/help', component: HelpView },
    { path: '/account', component: AccountView },
    { path: '/owner/login', component: OwnerLoginView },
    { path: '/owner', component: OwnerDashboardView },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
