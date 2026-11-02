// The live site has three addresses, so the owner's and customer's logins stay in separate
// cookies. In `npm run dev` these values are empty, and the links stay on one address.
export const SHOP_HOME = `${import.meta.env.VITE_SHOP_URL || ''}/`
export const OWNER_HOME = `${import.meta.env.VITE_OWNER_URL || ''}/owner`
export const PLANS_PAGE = `${import.meta.env.VITE_PLATFORM_URL || ''}/stylemate`
