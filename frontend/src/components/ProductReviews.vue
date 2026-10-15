<script setup>
// Reviews of one product. Anyone can read them; a customer who ordered the piece can write one.
import { reactive, ref, watch } from 'vue'
import { api } from '../api.js'
import { useAccount } from '../stores/account.js'
import { formatDate } from '../utils/format.js'

const props = defineProps({ code: { type: String, required: true } })
const account = useAccount()

const page = ref(null)
const form = reactive({ rating: 0, comment: '' })
const saving = ref(false)
const error = ref('')
const saved = ref(false)

const stars = (rating) => '★'.repeat(rating) + '☆'.repeat(5 - rating)

async function load() {
  error.value = ''
  saved.value = false
  try {
    page.value = await api(`/products/${encodeURIComponent(props.code)}/reviews`)
    clearForm() // the customer's own review is in the list above, not left in the box
  } catch (err) {
    error.value = err.message
  }
}
// Reload when the product changes, and when the customer logs in or out (it changes who may review)
watch([() => props.code, () => account.state.customer], load, { immediate: true })

function clearForm() {
  form.rating = 0
  form.comment = ''
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    page.value = await api(`/products/${encodeURIComponent(props.code)}/reviews`, {
      method: 'POST',
      body: { rating: form.rating, comment: form.comment },
    })
    saved.value = true
    clearForm() // posted: it now shows in the list, so the box starts empty again
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section id="reviews" class="reviews" aria-labelledby="reviews-title">
    <h2 id="reviews-title" class="title">Reviews</h2>

    <template v-if="page">
      <p v-if="page.count" class="summary">
        <span class="stars" aria-hidden="true">{{ stars(Math.round(page.average)) }}</span>
        <strong>{{ page.average }} out of 5</strong>
        <span class="muted">from {{ page.count }} {{ page.count === 1 ? 'review' : 'reviews' }}</span>
      </p>
      <p v-else class="muted">No reviews yet.</p>

      <ul v-if="page.count" class="list">
        <li v-for="(review, index) in page.reviews" :key="index">
          <p class="who">
            <span class="stars" :aria-label="`${review.rating} out of 5 stars`">{{ stars(review.rating) }}</span>
            <strong>{{ review.name }}</strong>
            <span class="muted small">{{ formatDate(review.reviewed_at) }} · Bought this piece</span>
          </p>
          <p v-if="review.comment" class="comment">{{ review.comment }}</p>
        </li>
      </ul>

      <form v-if="page.can_review" class="form" @submit.prevent="save">
        <h3>{{ page.my_review ? 'Change your review' : 'Write a review' }}</h3>
        <p v-if="page.my_review" class="muted small">Your review is shown above. Writing a new one replaces it.</p>
        <fieldset class="rating">
          <legend>Your rating</legend>
          <label v-for="value in 5" :key="value" class="star-choice" :class="{ on: value <= form.rating }">
            <input v-model.number="form.rating" type="radio" name="rating" :value="value" required class="visually-hidden" />
            <span aria-hidden="true">★</span><span class="visually-hidden">{{ value }} {{ value === 1 ? 'star' : 'stars' }}</span>
          </label>
        </fieldset>
        <div class="field">
          <label for="review-comment">Your review <span class="muted">(optional)</span></label>
          <textarea id="review-comment" v-model="form.comment" rows="3" maxlength="1000"
            placeholder="How did it fit? How does the fabric feel?"></textarea>
        </div>
        <button type="submit" class="button small" :disabled="saving || !form.rating">{{ saving ? 'Saving…' : 'Save review' }}</button>
        <p v-if="saved" class="message ok" role="status">Thank you. Your review is saved.</p>
      </form>
      <p v-else-if="page.blocked_reason === 'login'" class="muted">
        <RouterLink to="/account">Log in</RouterLink> to review a piece you’ve ordered.
      </p>
      <p v-else class="muted">You can review this piece after you’ve ordered it.</p>
    </template>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.reviews {
  margin-top: 56px;
  padding-top: 32px;
  border-top: 1px solid var(--line);
  max-width: 760px;
}
.title {
  font-size: var(--step-2);
  margin-bottom: 8px;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: baseline;
}
.stars {
  color: var(--haldi);
  letter-spacing: 2px;
}
.list {
  list-style: none;
  margin: 16px 0 0;
  padding: 0;
}
.list li {
  padding: 14px 0;
  border-top: 1px solid var(--line);
}
.who {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: baseline;
  margin: 0;
}
.comment {
  margin: 6px 0 0;
  white-space: pre-wrap;
}
.form {
  margin-top: 24px;
  padding: 20px;
  border-radius: 10px;
  background: var(--jamdani);
}
h3 {
  font-size: var(--step-1);
  margin-bottom: 10px;
}
.rating {
  border: 0;
  padding: 0;
  margin: 0 0 14px;
  display: flex;
  align-items: center;
  gap: 2px;
}
.rating legend {
  font-weight: 500;
  margin-bottom: 4px;
  padding: 0;
}
.star-choice {
  margin: 0;
  font-size: 1.75rem;
  line-height: 1;
  color: #cfc6c2;
  cursor: pointer;
}
.star-choice.on {
  color: var(--haldi);
}
.star-choice:focus-within {
  outline: 2px solid var(--indigo);
  outline-offset: 2px;
}
</style>
